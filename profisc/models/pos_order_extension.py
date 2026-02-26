import json
import logging
import textwrap
from collections import defaultdict
from datetime import date, datetime

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def userError(key, dict_ob):
    if key in dict_ob:
        raise UserError(dict_ob[key])
    raise UserError(json.dumps(dict_ob))


def get_difference_in_days(start_date):
    today_dt = datetime.now()
    return (today_dt - start_date).days


def generate_payment_methods(record):
    merged_list = []
    invoice_payments = []
    for pmt in record.payment_ids:
        payment_method = pmt.payment_method_id.profisc_payment_method
        invoice_pmt = {
            "paymentTerm": payment_method.code,
            "bankorCash": payment_method.name,
            "paymentAmount": pmt.amount
        }

        invoice_payments.append(invoice_pmt)
        merged_data = defaultdict(lambda: {"paymentTerm": "", "bankorCash": "", "paymentAmount": 0})
        for item in invoice_payments:
            key = item["bankorCash"]
            merged_data[key]["paymentTerm"] = item["paymentTerm"]
            merged_data[key]["bankorCash"] = item["bankorCash"]
            merged_data[key]["paymentAmount"] += item["paymentAmount"]
        merged_list = list(merged_data.values())

    return merged_list


class PosOrder(models.Model):
    _inherit = 'pos.order'

    profisc_fisc_type = fields.Char(string='Fiscalization Type', store=True)
    profisc_fisc_status = fields.Char(string='Fiscal Status', store=True)
    profisc_iic = fields.Char(string='IIC', store=True)
    profisc_fic = fields.Char(string='FIC')
    profisc_eic = fields.Char(string='EIC')
    profisc_qr_code = fields.Char(string='Qr Url')
    profisc_qr_code_check = fields.Binary(string='Qr Code', attachment=True)
    profisc_fisc_downloaded = fields.Boolean(string='Fiscal Downloaded')
    profisc_fic_error_code = fields.Char(string='FIC Error Code')
    profisc_fic_error_description = fields.Char(string='FIC Error Description')
    profisc_eic_error_code = fields.Char(string='EIC Error Code')
    profisc_eic_error_description = fields.Char(string='EIC Error Description')
    profisc_ubl_id = fields.Char(string='UBL ID')
    profisc_status_control = fields.Selection([('0', 'In Process'), ('2', 'Error'), ('3', 'Success'), ], store=True,
                                              string='Status Control')

    # BKT statuses
    profisc_bkt_status = fields.Char(string='BKT Status')
    profisc_bkt_paymentType = fields.Char(string='BKT Payment Type')
    profisc_bkt_amount = fields.Char(string='BKT Paid Amount')
    profisc_bkt_source = fields.Char(string='BKT Source')
    profisc_bkt_paymentMethod = fields.Char(string='BKT Payment Method')

    @api.model
    def get_reference_order(self, ordername):
        # ordername is in format Vila/0001 REFUND so we need to remove the REFUND preposition
        split_string = ordername.split()  # Splits the string on whitespace, creating a list ['Vila/0001', 'REFUND']
        desired_value = split_string[0]
        invoice = self.env['pos.order'].search(
            [('name', '=', desired_value)], limit=1)
        if invoice:
            return invoice.id
        return None

    @api.model
    def get_ref_order_id(self, ordername):
        invoice = self.env['pos.order'].search(
            [('name', '=', ordername)], limit=1)
        if invoice:
            return invoice
        return None

    @api.model
    def check_if_refund(self, ordername):
        split_string = ordername.split()  # Splits the string on whitespace, creating a list ['Vila/0001', 'REFUND']
        data = {
            'is_refund': False,
            'ref_name': ''
        }
        if len(split_string) > 1 and split_string[1] == 'REFUND':
            data['is_refund'] = True
            data['ref_name'] = split_string[0]
        return data

    @api.model
    def profisc_resend(self, subseq, invoice_ids):
        company = self.env['profisc.auth'].get_current_company()
        payload = {
            "object": "profisc_resend",
            "value": subseq,
            "username": self.env.user.name,
            "company": company.profisc_company_id,
            "invoice_ids": invoice_ids
        }
        _logger.info(f"profisc_resend %s", payload)
        for oid in invoice_ids:
            self.fiscalize_order(oid, subseq)

        return payload

    def action_show_update_profisc_subseq_wizard(self):
        return {
            'name': 'Update Profisc Subseq',
            'type': 'ir.actions.act_window',
            'res_model': 'profisc.pos_order_wizard',
            'view_mode': 'form',
            'view_id': self.env.ref('profisc.view_update_profisc_subseq_wizard').id,
            'target': 'new',
        }

    @api.model
    def get_invoice(self, order_ref):
        invoice = self.env['pos.order'].search(
            [('pos_reference', '=', order_ref)], limit=1)
        return {
            'profisc_ubl_id': invoice.profisc_ubl_id,
            'profisc_iic': invoice.profisc_iic,
            'profisc_fic': invoice.profisc_fic,
            'profisc_eic': invoice.profisc_eic,
            'profisc_qr_code': invoice.profisc_qr_code,
            'profisc_fic_error_code': invoice.profisc_fic_error_code,
            'profisc_fic_error_description': invoice.profisc_fic_error_description
        }

    @api.model
    def _order_fields(self, ui_order):
        fields = super(PosOrder, self)._order_fields(ui_order)

        # Include your custom field
        fields["profisc_fisc_type"] = ui_order.get("profisc_fisc_type", False)

        return fields

    @api.model
    def _process_order(self, order, draft, existing_order):
        order_id = super(PosOrder, self)._process_order(order, draft, existing_order)

        # Use the returned order_id to fetch the order record
        return self.fiscalize_order(order_id, 'n_a')

    @api.model
    def fiscalize_order(self, order_id, subseq):
        _logger.info('fiscalize_order with id: %s and subseq %s', order_id, subseq)
        pos_order = self.browse(order_id)
        profisc_fisc_type = int(pos_order.profisc_fisc_type)
        if profisc_fisc_type == 3:
            _logger.info("Creating FK...")
            return order_id

        company = self.env['profisc.auth'].get_current_company()
        invoice_payload = self.createInvoicePayload(pos_order)
        if subseq != 'n_a':
            invoice_payload['subseq'] = subseq

        auth_object = {
            "object": invoice_payload,
            "invoiceId": pos_order.access_token,
            "invoiceType": 'invoice',
            "isEinvoice": int(pos_order.profisc_fisc_type) == 2,
        }
        _logger.info('pos_order.profisc_fisc_type:: %s' % pos_order.profisc_fisc_type)
        _logger.info('request:: %s' % auth_object)
        response = requests.post(f"{company.profisc_api_endpoint}{company.profisc_upload_invoice}",
                                 data=json.dumps(auth_object),
                                 headers=self.env['profisc.auth'].generateHeaders())
        res = response.json()
        _logger.info('response:: %s' % res)
        self.handleResponse(pos_order, res, response, subseq)
        # Call the super function to ensure original functionalities are retained
        return order_id

    def handleResponse(self, record, res, response, subseq):
        _logger.info('response.status_code:: %s!' % response.status_code)

        if response.status_code == 200:
            if res['status'] and res['errorCode'] is None:
                self.updateRecord(record, res)
                # self.getQrCode(record.id)
                # self.info(record.id, "Fiskalizim i suksesshem")

            elif res['errorCode'] == 'T991':
                record.write({
                    'profisc_status_control': '2',
                    'profisc_fisc_status': 'E' + res['errorCode'],
                    'profisc_fic_error_code': res['errorCode'],
                    'profisc_eic_error_description': res['faultDescription'],
                    'profisc_iic': res['iic'],
                    'profisc_fic': res['fic'],
                    'profisc_eic': res['eic'],
                    'profisc_qr_code': res['qrUrl']
                })
                self.env.cr.commit()

            elif res['errorCode'] == 'T010':
                self.updateRecord(record, res)

            else:
                record.write({
                    'profisc_status_control': '0',
                    'profisc_fisc_status': 'E' + res['errorCode'],
                    'profisc_fic_error_code': res['errorCode'],
                    'profisc_fic_error_description': res['faultDescription']
                })
                self.env.cr.commit()
                userError('faultDescription', res)

            # raise UserError("Error with code:"+res['errorCode']+", description:"+res['faultDescription'])
        elif response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            self.fiscalize_order(record.id, subseq)
        else:
            userError('faultDescription', res)

    def updateRecord(self, record, res):
        record.write({
            'profisc_iic': res['iic'],
            'profisc_fic': res['fic'],
            'profisc_eic': res['eic'],
            'profisc_qr_code': res['qrUrl'],
            'profisc_status_control': '3',
            'profisc_fisc_status': 'Y',
            'profisc_fic_error_code': '100',
            'profisc_fic_error_description': '',
            'profisc_ubl_id': res['ublId']

        })
        self._force_create_invoice(record)

    def createInvoicePayload(self, record):
        ref_order = None
        odata = self.check_if_refund(record.name)
        if odata['is_refund']:
            ref_order = self.get_ref_order_id(odata['ref_name'])
            if not ref_order.profisc_iic:
                ref_order = None

        current_time = datetime.now().strftime("%H:%M:%S")

        invoice_json = {
            "invoiceId": record.access_token,
            'date': str(record.date_order.strftime("%d/%m/%Y ") + current_time),
            'dueDate': str(record.date_order.strftime("%d/%m/%Y ") + current_time),
            'invoiceCode': 388 if not ref_order else 384,
            'invoiceType': 'invoice' if not ref_order else 'credit',
            'currency': "ALL",
            'exchangeRate': 1,
            'sendEInv': int(record.profisc_fisc_type) == 2,
            'taxScheme': "Normal",
            'profileId': 'P1' if not ref_order else 'P10',
            'noteToCustomer': "",
            'customer': {
                "name": "Klient i pergjithshem",
                "nipt": "T12345678P",
                "address": "Tirane",
                "cityName": "Tirane",
                "countryCode": "ALB",
                "idType": "ID"
            },
            "seller": {
                "name": record.company_id.display_name,
                "nipt": record.company_id.vat,
                "address": record.company_id.street,
                "cityName": record.company_id.city,
                "countryCode": self.env['other_functions'].convert_country_code(record.company_id.country_code),
                # record.company_id.country_code
            },
            "paymentMethods": [],
            'items': [],
            'totalNeto': record.amount_total - record.amount_tax,
            'totalVat': record.amount_tax,
            'total': record.amount_total
        }
        if ref_order:
            invoice_json['refIic'] = str(ref_order.profisc_iic)  # new corrective
            invoice_json['refIssueDate'] = str(ref_order.write_date.strftime("%Y-%m-%d"))

        if record.config_id.tcr_code:
            invoice_json['tcr'] = record.config_id.tcr_code

        # if record.employee_id.

        if record.employee_id.profisc_operator_code:
            operator_code = record.employee_id.profisc_operator_code
        else:
            operator_code = record.user_id.profisc_operator_code

        if operator_code:
            invoice_json['operatorCode'] = operator_code

        _logger.info(f"operatorCode::{record.employee_id.profisc_operator_code}, name::{record.employee_id.name}")

        if record.partner_id.name:
            customer = {
                "name": record.partner_id.name,
                "nipt": record.partner_id.vat,
                "address": record.partner_id.street,
                "cityName": record.partner_id.city,
                "countryCode": self.env['other_functions'].convert_country_code(record.partner_id.country_code),
            }
            if record.partner_id.profisc_customer_vat_type:
                customer[
                    'idType'] = record.partner_id.profisc_customer_vat_type if record.partner_id.profisc_customer_vat_type else "id"
            else:
                customer['idType'] = "9923"

            invoice_json['customer'] = customer

        if len(record.payment_ids) > 0:
            invoice_payments = generate_payment_methods(record)
            invoice_json['paymentMethods'] = invoice_payments

        for line in record.lines:

            tax = line.tax_ids
            price_include = tax.price_include

            if line.customer_note:
                invoice_json['noteToCustomer'] += line.customer_note
                invoice_json['noteToCustomer'] += " "

            item_price = line.price_unit
            total_line_neto = line.price_subtotal

            if price_include:
                item_price = line.price_unit / (1 + tax.amount / 100)

            total_line_vat = total_line_neto * (1 + tax.amount / 100) - total_line_neto  # formula e pare

            coef = 1

            uom_code = line.product_uom_id.profisc_uom_val.code if line.product_uom_id.profisc_uom_val else line.product_uom_id.name

            invoice_line = {
                'code': str(line.id),
                'name': textwrap.shorten(line.full_product_name, width=50, placeholder="..."),
                "unit": uom_code,
                'quantity': coef * line.qty,
                'price': item_price,
                "discount": line.discount,  #
                "vat": tax.amount,
                "vatScheme": tax.description,
                "totalLineNeto": coef * total_line_neto,
                "totalLineVat": coef * total_line_vat
            }

            _logger.info(f"uom_code:{uom_code}")
            invoice_json['items'].append(invoice_line)

        self.set_sub_seq(invoice_json)

        return invoice_json

    def _create_invoice(self, move_vals):  # Match original signature
        # Call super to get the original functionality for creating an invoice

        invoice = super(PosOrder, self)._create_invoice(move_vals)

        _logger.info("Method _create_invoice is called %id" % invoice.id)
        _logger.info("Creating Invoice for Order(s): %s", self.ids)
        for order in self:
            invoice.write({
                'profisc_iic': order.profisc_iic,
                'profisc_fic': order.profisc_fic,
                'profisc_eic': order.profisc_eic,
                'profisc_qr_code': order.profisc_qr_code,
                'profisc_status_control': order.profisc_status_control,
                'profisc_fisc_status': order.profisc_fisc_status,
                'profisc_fic_error_code': order.profisc_fic_error_code,
                'profisc_fic_error_description': order.profisc_fic_error_description,
                'profisc_ubl_id': order.profisc_ubl_id
            })

            _logger.info(
                f"Method _create_invoice is called invoice.profisc_iic::{invoice.profisc_iic}, order.profisc_iic::{order.profisc_iic}")

        # Return the modified invoice
        return invoice

    def _force_create_invoice(self, order):  # Match original signature
        # Call super to get the original functionality for creating an invoice

        # invoice = super(PosOrder, self)._create_invoice(move_vals)

        _logger.info("Calling method _force_create_invoice")
        _logger.info(f"_force_create_invoice:: working with id={order.id}")
        if order.to_invoice:
            _logger.info(f"_force_create_invoice:: working with id={order.id} is ready for creating invoice")
            invoice = self.env['account.move'].search(
                [('id', '=', order.account_move.id)], limit=1)

            _logger.info("Method _force_create_invoice is called %id" % invoice.id)
            invoice.write({
                'profisc_iic': order.profisc_iic,
                'profisc_fic': order.profisc_fic,
                'profisc_eic': order.profisc_eic,
                'profisc_qr_code': order.profisc_qr_code,
                'profisc_status_control': order.profisc_status_control,
                'profisc_fisc_status_sale': order.profisc_fisc_status,
                'profisc_fic_error_code': order.profisc_fic_error_code,
                'profisc_fic_error_description': order.profisc_fic_error_description,
                'profisc_ubl_id': order.profisc_ubl_id
            })

            _logger.info(
                f"Updated values invoice.profisc_iic::{invoice.profisc_iic}, order"
                f".profisc_iic::{order.profisc_iic}")
            return invoice
        else:
            _logger.info(
                "The param 'to_invoice' must be checked in order to create invoice for Order with id=%s",
                order.id)
            return None

    def set_sub_seq(self, invoice_json):
        company = self.env['profisc.auth'].get_current_company()
        if company.profisc_auto_subseq:
            invoice_date_string = invoice_json['date']
            issue_date = datetime.strptime(invoice_date_string, '%d/%m/%Y %H:%M:%S')
            days_difference = get_difference_in_days(issue_date)
            subseq = None
            if days_difference > 0:
                today_dt = datetime.now()
                if days_difference < 2:
                    subseq = "SERVICE"
                elif days_difference <= 10:
                    subseq = "BOUNDBOOK"
                else:
                    if (today_dt.year == issue_date.year and
                            (today_dt.month == issue_date.month or
                             (today_dt.month - issue_date.month) <= 1 and today_dt.day <= 10)):
                        subseq = "NOINTERNET"
                    elif (today_dt.year - issue_date.year == 1 and
                          today_dt.month == 1 and issue_date.month == 12 and today_dt.day <= 10):
                        subseq = "NOINTERNET"
                if subseq:
                    invoice_json['subseq'] = subseq

        return invoice_json

    def get_BKT_status(self, iic, bill=None, company_id=None):
        company = self.env['res.company'].browse(company_id)
        auth_object = {
            "object": "PaymentReceipt",
            "params": json.dumps({"iic": iic}),
            "username": self.env.user.name,
            "company": company.profisc_company_id
        }
        res = requests.post(f"{company.profisc_api_endpoint}{company.profisc_search_endpoint}",
                            data=json.dumps(auth_object),
                            headers=self.env['profisc.auth'].generateHeadersBkt(company))

        if res.status_code == 200:
            _logger.info(res.json())
            order = self.handle_BKT_response(res.json(), bill)
            print(res.json())
            return {
                'profisc_bkt_status': order.profisc_bkt_status,
                'profisc_bkt_paymentType': order.profisc_bkt_paymentType,
                'profisc_bkt_amount': order.profisc_bkt_amount,
                'profisc_bkt_source': order.profisc_bkt_source,
                'profisc_bkt_paymentMethod': order.profisc_bkt_paymentMethod,
            }
        if res.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            self.get_BKT_status(iic, company_id)
        else:
            raise UserError(res.text)

    def handle_BKT_response(self, response, bill=None):

        if response['status'] and len(response['content']) > 0:
            object = response['content'][0]
            if bill == None:
                bill = self.env['pos.order'].search([('profisc_iic', '=', object['iic'])])
                print(bill.profisc_iic)
                bill.write({
                    'profisc_bkt_status': object.get('invoiceInternalPaymentStatus'),
                    'profisc_bkt_paymentType': object['paymentType'],
                    'profisc_bkt_amount': object['amount'],
                    'profisc_bkt_source': object['source'],
                    'profisc_bkt_paymentMethod': object['paymentMethod']
                })
            else:
                bill.write({
                    'profisc_bkt_status': object.get('invoiceInternalPaymentStatus'),
                    'profisc_bkt_paymentType': object['paymentType'],
                    'profisc_bkt_amount': object['amount'],
                    'profisc_bkt_source': object['source'],
                    'profisc_bkt_paymentMethod': object['paymentMethod']
                })

        return bill