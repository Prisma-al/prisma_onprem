# -*- coding: utf-8 -*-

import logging
import pprint
import re
import time
from urllib.parse import quote as url_quote

from odoo import fields, models, _, SUPERUSER_ID
from odoo.exceptions import ValidationError
from odoo.http import request


_logger = logging.getLogger(__name__)

# RaiAccept phone regex: empty, international (+/00 prefix), or 8-16 digits
_PHONE_RE = re.compile(r'^$|^(\+|00)[1-9]\d{1,3}\d{6,11}$|^\d{8,16}$')


def _sanitize_phone(value):
    """Return the phone string if it matches RaiAccept's format, else empty string."""
    if not value:
        return ''
    digits = re.sub(r'[\s\-().]+', '', value)  # strip formatting
    if _PHONE_RE.match(digits):
        return digits
    return ''


# Mapping of ISO 3166-1 alpha-2 to alpha-3 country codes (common countries)
COUNTRY_ALPHA2_TO_ALPHA3 = {
    'AL': 'ALB', 'AD': 'AND', 'AT': 'AUT', 'BA': 'BIH', 'BE': 'BEL',
    'BG': 'BGR', 'HR': 'HRV', 'CY': 'CYP', 'CZ': 'CZE', 'DK': 'DNK',
    'EE': 'EST', 'FI': 'FIN', 'FR': 'FRA', 'DE': 'DEU', 'GR': 'GRC',
    'HU': 'HUN', 'IS': 'ISL', 'IE': 'IRL', 'IT': 'ITA', 'XK': 'XKX',
    'LV': 'LVA', 'LI': 'LIE', 'LT': 'LTU', 'LU': 'LUX', 'MT': 'MLT',
    'MD': 'MDA', 'MC': 'MCO', 'ME': 'MNE', 'NL': 'NLD', 'MK': 'MKD',
    'NO': 'NOR', 'PL': 'POL', 'PT': 'PRT', 'RO': 'ROU', 'RU': 'RUS',
    'SM': 'SMR', 'RS': 'SRB', 'SK': 'SVK', 'SI': 'SVN', 'ES': 'ESP',
    'SE': 'SWE', 'CH': 'CHE', 'TR': 'TUR', 'UA': 'UKR', 'GB': 'GBR',
    'US': 'USA', 'CA': 'CAN', 'AU': 'AUS', 'NZ': 'NZL', 'JP': 'JPN',
    'CN': 'CHN', 'IN': 'IND', 'BR': 'BRA', 'MX': 'MEX', 'AR': 'ARG',
    'ZA': 'ZAF', 'EG': 'EGY', 'AE': 'ARE', 'SA': 'SAU', 'IL': 'ISR',
}


def _get_alpha3_code(country):
    """Convert Odoo country (alpha-2) to ISO 3166-1 alpha-3 code. Defaults to ALB."""
    if not country:
        return 'ALB'
    return COUNTRY_ALPHA2_TO_ALPHA3.get(country.code, country.code or 'ALB')


class PaymentTransactionRaiAccept(models.Model):
    _inherit = 'payment.transaction'

    raiaccept_order_id = fields.Char(string='RaiAccept Order ID')
    raiaccept_session_id = fields.Char(string='RaiAccept Session ID')

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_id.code != 'rai_accept':
            return res

        provider = self.provider_id
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')

        # Try to get sale order from website context (eCommerce flow)
        order = None
        if hasattr(request, 'website') and request.website:
            try:
                order = request.website.sale_get_order()
            except Exception:
                pass
        if not order and request and hasattr(request, 'session'):
            sale_order_id = request.session.get('sale_last_order_id')
            if sale_order_id:
                order = self.env['sale.order'].sudo().browse(sale_order_id).exists()

        # Resolve partner, amount, description, and items from order or invoice
        partner = self.partner_id
        amount = self.amount
        description = self.reference
        items = []

        if order and order.exists():
            partner = order.partner_id
            amount = order.amount_total
            description = 'Order %s' % order.name
            items = [{
                'description': line.product_id.name or line.name,
                'numberOfItems': max(int(line.product_uom_qty), 1),
                'price': round(line.price_total / max(line.product_uom_qty, 1), 2),
            } for line in order.order_line if not line.is_downpayment and line.price_total]
        elif self.invoice_ids:
            invoice = self.invoice_ids[0]
            partner = invoice.partner_id or partner
            amount = invoice.amount_total
            description = 'Invoice %s' % invoice.name
            items = [{
                'description': line.name or 'Product',
                'numberOfItems': max(int(line.quantity), 1),
                'price': round(line.price_total / max(line.quantity, 1), 2),
            } for line in invoice.invoice_line_ids if line.display_type == 'product' and line.price_total]

        if not items:
            items = [{'description': description, 'numberOfItems': 1, 'price': float(amount)}]

        # Sanitize reference for merchantOrderReference (alphanumeric, hyphens, underscores only)
        # Add timestamp to ensure uniqueness for retried payments
        merchant_ref = re.sub(r'[^a-zA-Z0-9_-]', '-', self.reference) + '-' + str(int(time.time()))
        # URL-encode the Odoo reference for use in redirect URLs
        encoded_ref = url_quote(self.reference, safe='')

        # Step 1: Authenticate
        token = provider._raiaccept_authenticate()

        # Build order data payload
        first_name = partner.name.split(' ')[0] if partner.name else ''
        last_name = ' '.join(partner.name.split(' ')[1:]) if partner.name and ' ' in partner.name else ''

        order_data = {
            'consumer': {
                'firstName': first_name,
                'lastName': last_name or first_name,
                'email': partner.email or '',
                'mobilePhone': _sanitize_phone(partner.phone),
                'phone': _sanitize_phone(partner.phone),
            },
            'billingAddress': {
                'firstName': first_name,
                'lastName': last_name or first_name,
                'addressStreet1': partner.street or '',
                'addressStreet2': partner.street2 or '',
                'city': partner.city or '',
                'postalCode': partner.zip or '',
                'country': _get_alpha3_code(partner.country_id),
                'state': (partner.state_id.code or '')[:3],
            },
            'invoice': {
                'amount': amount,
                'currency': provider.raiaccept_currency,
                'description': description,
                'merchantOrderReference': merchant_ref,
                'items': items,
            },
            'paymentMethodPreference': 'CARD',
            'shippingAddress': {
                'firstName': first_name,
                'lastName': last_name or first_name,
                'addressStreet1': partner.street or '',
                'addressStreet2': partner.street2 or '',
                'city': partner.city or '',
                'postalCode': partner.zip or '',
                'country': _get_alpha3_code(partner.country_id),
                'state': (partner.state_id.code or '')[:3],
            },
            'urls': {
                'successUrl': '%s/payment/rai_accept/success?reference=%s' % (base_url, encoded_ref),
                'failUrl': '%s/payment/rai_accept/failed?reference=%s' % (base_url, encoded_ref),
                'cancelUrl': '%s/payment/rai_accept/cancel?reference=%s' % (base_url, encoded_ref),
                'notificationUrl': '%s/payment/rai_accept/webhook' % base_url,
            },
        }

        _logger.info("RaiAccept order data:\n%s", pprint.pformat(order_data, indent=2))

        # Step 2: Create order in RaiAccept
        order_result = provider._raiaccept_create_order(token, order_data)
        order_identification = order_result.get('orderIdentification')

        # Store the order ID on the transaction
        self.sudo().write({
            'raiaccept_order_id': order_identification,
        })

        # Step 3: Create payment session
        session_result = provider._raiaccept_create_payment_session(
            token, order_identification, order_data
        )
        payment_redirect_url = session_result.get('paymentRedirectURL')
        session_id = session_result.get('sessionId')

        self.sudo().write({
            'raiaccept_session_id': session_id,
        })

        _logger.info(
            "RaiAccept payment session created for reference %s: redirect to %s",
            self.reference, payment_redirect_url,
        )

        rendering_values = {
            'api_url': 'https://payment.raiaccept.com/checkout',
            'payment_session': session_id,
        }
        return rendering_values

    def _finalize_post_processing(self):
        """Ensure all post-processing runs under admin context, not the browser session user."""
        if self.env.uid != SUPERUSER_ID:
            return self.with_user(SUPERUSER_ID)._finalize_post_processing()
        result = super()._finalize_post_processing()
        self.env.flush_all()
        return result

    def _reconcile_after_done(self):
        """Override to force-create invoices, fiscalise, and send invoice email with QR codes."""
        if self.env.uid != SUPERUSER_ID:
            return self.with_user(SUPERUSER_ID)._reconcile_after_done()

        rai_txs = self.filtered(
            lambda t: t.provider_code == 'rai_accept' and t.sale_order_ids
        )

        # Confirm orders early so we can invoice them
        if hasattr(rai_txs, '_check_amount_and_confirm_order'):
            rai_txs._check_amount_and_confirm_order()
        else:
            # Odoo 19: confirm sale orders directly
            for tx in rai_txs:
                for so in tx.sale_order_ids.filtered(lambda o: o.state in ('draft', 'sent')):
                    so.action_confirm()

        # Force create invoices BEFORE super() so payment base can reconcile them
        for tx in rai_txs:
            tx_c = tx.with_company(tx.company_id)
            if not tx_c.invoice_ids:
                if hasattr(tx_c, '_invoice_sale_orders'):
                    tx_c._invoice_sale_orders()
                else:
                    # Odoo 19: create invoices directly from sale orders
                    for so in tx_c.sale_order_ids.filtered(lambda o: o.state == 'sale'):
                        so._create_invoices()

        # Post, fiscalise, and send invoice email BEFORE super() reconciles.
        # Once reconciled, profisc's _compute_taxes triggers a write on the
        # reconciled move that Odoo blocks with "not balanced" error.
        for tx in rai_txs:
            tx_c = tx.with_company(tx.company_id)
            # marrim acc payment term-in
            acc_pm_term = self.env['account.payment.term'].search([('name', '=', 'Cash BANK Card Profisc')], limit=1)
            for invoice in tx_c.invoice_ids.filtered(lambda i: i.state == 'draft'):
                invoice.sudo().write({'invoice_payment_term_id': acc_pm_term.id})
                invoice.action_post()
            for invoice in tx_c.invoice_ids.filtered(lambda i: i.state == 'posted'):
                try:
                    self._fiscalize_invoice(invoice)
                except Exception as e:
                    _logger.error("RaiAccept: Failed to fiscalise invoice %s: %s", invoice.name, str(e))
                try:
                    tx_c._send_invoice_with_qr_codes(invoice)
                except Exception as e:
                    _logger.error("RaiAccept: Failed to send invoice email %s: %s", invoice.name, str(e))

        # super() will: re-confirm (idempotent), skip auto-invoice,
        # payment base sees already-posted invoices, creates payment + reconciles.
        # Disable tracking to prevent wrong user attribution on payment messages.
        super(PaymentTransactionRaiAccept, self.with_context(
            tracking_disable=True,
            mail_notrack=True,
            mail_create_nolog=True,
        ))._reconcile_after_done()

    def _fiscalize_invoice(self, invoice):
        """Set profisc fields on the invoice and send it to profisc for fiscalization."""
        inv = invoice.sudo()

        # Skip if already fiscalized
        if inv.profisc_fic:
            _logger.info("RaiAccept: Invoice %s already fiscalized (FIC: %s)", inv.name, inv.profisc_fic)
            return

        # Set profisc fields required for fiscalization
        vals = {
            'profisc_cis_type': '-1',  # Fiscalization
            'profisc_invoice_type': '380',  # Commercial
            'profisc_profile_id': 'P1',
            'profisc_status_control': '0',
        }

        if not inv.invoice_date:
            vals['invoice_date'] = fields.Date.today()

        # Set TCR code from first available selection value if not already set
        if not inv.profisc_tcr_code:
            tcr_selection = inv.fields_get('profisc_tcr_code')['profisc_tcr_code'].get('selection', [])
            if tcr_selection:
                vals['profisc_tcr_code'] = tcr_selection[0][0]

        # Set Business Unit code from first available selection value if not already set
        if not inv.profisc_bu_code:
            bu_selection = inv.fields_get('profisc_bu_code')['profisc_bu_code'].get('selection', [])
            if bu_selection:
                vals['profisc_bu_code'] = bu_selection[0][0]


        inv.write(vals)
        _logger.info("RaiAccept: Set profisc fields on invoice %s: %s", inv.name, vals)

        # Send to profisc for fiscalization (with_company sets company_id in
        # context so profisc.auth.get_current_company() can resolve it)
        self.env['profisc.actions'].sudo().with_company(inv.company_id).sendToProfisc(inv.id)
        _logger.info("RaiAccept: Fiscalization sent for invoice %s", inv.name)

    def _send_invoice_with_qr_codes(self, invoice):
        """Send invoice email with fiscal QR code attached."""
        self.ensure_one()

        # Get invoice email template (same source as Odoo's _send_invoice)
        template_id = int(self.env['ir.config_parameter'].sudo().get_param(
            'sale.default_invoice_email_template', default=0
        ))
        template = self.env['mail.template'].browse(template_id).exists() if template_id else None
        if not template:
            template = self.env.ref('account.email_template_edi_invoice', raise_if_not_found=False)
        if not template:
            _logger.warning("RaiAccept: No invoice email template found, skipping email")
            return

        extra_attachments = self.env['ir.attachment']

        # Fiscal QR code image (set by profisc after fiscalisation)
        if invoice.profisc_qr_code_check:
            fiscal_qr_att = self.env['ir.attachment'].sudo().create({
                'name': 'Fiscal QR - %s.png' % invoice.name,
                'type': 'binary',
                'datas': invoice.profisc_qr_code_check,
                'res_model': 'account.move',
                'res_id': invoice.id,
                'mimetype': 'image/png',
            })
            extra_attachments |= fiscal_qr_att

        # Temporarily add extra attachments to template, send, then clean up
        if extra_attachments:
            template.attachment_ids = [(4, att.id) for att in extra_attachments]

        template.send_mail(invoice.id, force_send=True)

        if extra_attachments:
            template.attachment_ids = [(5,)]

        invoice.is_move_sent = True
        _logger.info(
            "RaiAccept: Invoice email sent for %s with %d extra attachments",
            invoice.name, len(extra_attachments),
        )

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        if provider_code != 'rai_accept':
            return super()._get_tx_from_notification_data(provider_code, notification_data)

        reference = notification_data.get('reference')
        if not reference:
            raise ValidationError(_("RaiAccept: Received data with missing reference."))

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'rai_accept')])
        if not tx:
            raise ValidationError(
                _("RaiAccept: No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        if self.provider_code != 'rai_accept':
            return super()._process_notification_data(notification_data)
        if self.env.uid != SUPERUSER_ID:
            return self.with_user(SUPERUSER_ID)._process_notification_data(notification_data)

        provider = self.provider_id
        order_identification = self.raiaccept_order_id

        if not order_identification:
            _logger.error("RaiAccept: No order ID found for transaction %s", self.reference)
            self._set_error(_("RaiAccept: No order ID found for this transaction."))
            return

        # Verify order status with RaiAccept API
        try:
            token = provider._raiaccept_authenticate()
            order_details = provider._raiaccept_get_order_status(token, order_identification)
            order_status = order_details.get('status', '')
            _logger.info("RaiAccept order status for %s: %s", order_identification, order_status)

            # Get transaction details
            tx_data = provider._raiaccept_get_transactions(token, order_identification)

            # Store payment record
            payment_vals = {
                'order_identification': order_identification,
                'merchant_order_reference': order_details.get('invoice', {}).get('merchantOrderReference', ''),
                'amount': order_details.get('invoice', {}).get('amount', 0),
                'currency': order_details.get('invoice', {}).get('currency', ''),
                'status': order_status,
                'payment_method': 'CARD',
            }

            if tx_data and isinstance(tx_data, list):
                for tx_item in tx_data:
                    if tx_item.get('transactionType') == 'PURCHASE':
                        payment_vals.update({
                            'transaction_id': tx_item.get('transactionId', ''),
                            'transaction_type': tx_item.get('transactionType', ''),
                            'status_code': tx_item.get('statusCode', ''),
                            'status_message': tx_item.get('statusMessage', ''),
                            'created_on': tx_item.get('createdOn', ''),
                            'updated_on': tx_item.get('updatedOn', ''),
                        })
                        break
            elif tx_data and isinstance(tx_data, dict):
                payment_vals.update({
                    'transaction_id': tx_data.get('transactionId', ''),
                    'transaction_type': tx_data.get('transactionType', ''),
                    'status_code': tx_data.get('statusCode', ''),
                    'status_message': tx_data.get('statusMessage', ''),
                    'created_on': tx_data.get('createdOn', ''),
                    'updated_on': tx_data.get('updatedOn', ''),
                })

            self.env['raiaccept.payments'].sudo().create(payment_vals)
            self.provider_reference = order_identification

        except Exception as e:
            _logger.error("RaiAccept: Failed to verify order status: %s", str(e))
            self._set_error(_("RaiAccept: Could not verify payment with RaiAccept API. Please check manually."))
            return

        # Set the transaction state based on API-verified order status
        api_status = order_details.get('status', '') if order_details else ''
        if api_status in ('PAID', 'SUCCESS', 'COMPLETED'):
            self._set_done()
            _logger.info("RaiAccept: Transaction %s set to done (API verified: %s)", self.reference, api_status)
        elif api_status in ('CANCELED', 'ABANDONED'):
            self._set_canceled(_("Payment was cancelled by the customer."))
            _logger.info("RaiAccept: Transaction %s cancelled (API verified: %s)", self.reference, api_status)
        else:
            status = notification_data.get('status', '')
            if status == 'cancel':
                self._set_canceled(_("Payment was cancelled by the customer."))
            else:
                self._set_error(_("RaiAccept: Payment not confirmed. API status: %s", api_status or 'unknown'))
            _logger.info("RaiAccept: Transaction %s failed with status: %s", self.reference, status)
