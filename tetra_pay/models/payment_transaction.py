import base64
import binascii
import collections, re
import logging
import pprint
import random
import hashlib

from odoo.exceptions import ValidationError
from odoo.http import request

from odoo import models, _
from odoo.addons.payment import utils as payment_utils

_logger = logging.getLogger(__name__)

globvar = 0


class payment_transaction(models.Model):
    """ Handles the functions for validation after transaction is processed """
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        print("Entered:: _get_specific_rendering_values")
        res = super()._get_specific_rendering_values(processing_values)

        if self.provider_id.code != 'tetra_pay':
            return res

        order = self.env['sale.order'].sudo().browse(request.session.get('sale_last_order_id'))
        order.reference = self.reference
        payment_provider = self.env['payment.provider'].sudo().search([('code', '=', 'tetra_pay')], limit=1)
        rnd = random.randint(1000000000, 2000000000)

        rendering_values = {
            'clientid': payment_provider.tpay_clientid,
            'oid': self.reference,
            'amount': format(order.amount_total, '.0f'),
            'okUrl': payment_provider.tpay_ok_url,
            'failUrl': payment_provider.tpay_fail_url,
            'api_url': self.provider_id._get_mygateway_form_action_url(),
            'trantype': payment_provider.tpay_trantype,
            'rnd': rnd,
            'storetype': payment_provider.tpay_storetype,
            'currency': '008',
            'email': order.partner_id.email,
            'billtoname': order.partner_id.name,
            'refreshtime': payment_provider.tpay_refreshtime,
            # 'lang': 'en',
            'encoding': payment_provider.tpay_encoding,
            'hashAlgorithm': payment_provider.tpay_hash_algorithm,
            'instalment': '0',
        }

        hash_value = self._generate_hash(rendering_values, payment_provider.tpay_storekey)
        rendering_values['hash'] = hash_value
        return rendering_values

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Adyen data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if inconsistent data were received
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'tetra_pay' or len(tx) == 1:
            return tx

        hash = notification_data.get('hash') or notification_data.get('HASH')
        if not hash:
            raise ValidationError("Tetra Pay: " + _("Received data with missing hash"))
        reference = notification_data.get('oid')
        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'tetra_pay')])

        _logger.info("Tetra Pay: _get_tx_from_notification_data:: %s" % pprint.pformat(tx.state))
        if not tx:
            raise ValidationError(
                "Tetra Pay: " + _("No transaction found matching reference %s.", reference)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """ Process the notification data received from the provider.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'tetra_pay':
            return

        tetrapay_payments = self.env['tetrapay.payments'].sudo().create({
            'ACQBIN': notification_data.get('ACQBIN'),
            'AuthCode': notification_data.get('AuthCode'),
            'BillToName': notification_data.get('BillToName'),
            'CARDBRAND': notification_data.get('EXTRA.CARDBRAND'),
            'CARDISSUER': notification_data.get('EXTRA.CARDISSUER'),
            'TRXDATE': notification_data.get('EXTRA.TRXDATE'),
            'ExpDate_Month': notification_data.get('Ecom_Payment_Card_ExpDate_Month'),
            'ExpDate_Year': notification_data.get('Ecom_Payment_Card_ExpDate_Year'),
            'ErrMsg': notification_data.get('ErrMsg'),
            'HASH': notification_data.get('HASH'),
            'HostRefNum': notification_data.get('HostRefNum'),
            'MaskedPan': notification_data.get('MaskedPan'),
            'ReturnOid': notification_data.get('ReturnOid'),
            'SettleId': notification_data.get('SettleId'),
            'RReqExtensions': notification_data.get('TDS2.RReqExtensions'),
            'acsOperatorID': notification_data.get('TDS2.acsOperatorID'),
            'acsReferenceNumber': notification_data.get('TDS2.acsReferenceNumber'),
            'acsTransID': notification_data.get('TDS2.acsTransID'),
            'authTimestamp': notification_data.get('TDS2.authTimestamp'),
            'authenticationType': notification_data.get('TDS2.authenticationType'),
            'dsTransID': notification_data.get('TDS2.dsTransID'),
            'threeDSServerTransID': notification_data.get('TDS2.threeDSServerTransID'),
            'transStatus': notification_data.get('TDS2.transStatus'),
            'TRANID': notification_data.get('TRANID'),
            'TransId': notification_data.get('TransId'),
            'acqStan': notification_data.get('acqStan'),
            'amount': notification_data.get('amount'),
            'callbackCall': notification_data.get('callbackCall'),
            'cavv': notification_data.get('cavv'),
            'clientIp': notification_data.get('clientIp'),
            'clientid': notification_data.get('clientid'),
            'currency': notification_data.get('currency'),
            'digest': notification_data.get('digest'),
            'dsId': notification_data.get('dsId'),
            'eci': notification_data.get('eci'),
            'email': notification_data.get('email'),
            'encoding': notification_data.get('encoding'),
            'failUrl': notification_data.get('failUrl'),
            'fismi': notification_data.get('fismi'),
            'hashAlgorithm': notification_data.get('hashAlgorithm'),
            'maskedCreditCard': notification_data.get('maskedCreditCard'),
            'md': notification_data.get('md'),
            'mdErrorMsg': notification_data.get('mdErrorMsg'),
            'mdStatus': notification_data.get('mdStatus'),
            'merchantID': notification_data.get('merchantID'),
            'merchantName': notification_data.get('merchantName'),
            'oid': notification_data.get('oid'),
            'okUrl': notification_data.get('okUrl'),
            'paresTxStatus': notification_data.get('paresTxStatus'),
            'dsId': notification_data.get('dsId'),
            'protocol': notification_data.get('protocol'),
            'querypointhash': notification_data.get('querypointhash'),
            'refreshtime': notification_data.get('refreshtime'),
            'rnd': notification_data.get('rnd'),
            'sID': notification_data.get('sID'),
            'signature': notification_data.get('signature'),
            'storetype': notification_data.get('storetype'),
            'trantype': notification_data.get('trantype'),
            'cavvAlgorthm': notification_data.get('cavvAlgorthm'),
            'userselectedinstalment': notification_data.get('userselectedinstalment'),
            'veresEnrolledStatus': notification_data.get('veresEnrolledStatus'),
            'version': notification_data.get('version'),
            'x': notification_data.get('x'),
            'xid': notification_data.get('xid'),
            'y': notification_data.get('y'),
        })

        self.provider_reference = notification_data.get('clientid')

        status = notification_data.get('ProcReturnCode')

        payment_method_type = notification_data.get('ProcReturnCode')
        payment_method = self.env['payment.method']._get_from_code(payment_method_type)
        self.payment_method_id = payment_method or self.payment_method_id
        order = self.env['sale.order'].sudo().search([('reference', '=', notification_data.get('oid'))])

        _logger.info("Tetra Pay: _process_notification_data:: %s" % pprint.pformat(self.payment_method_id))
        _logger.info("Tetra Pay: sale.order:: %s" % pprint.pformat(order))

        if status == '00':
            self._set_done()
            order.action_confirm()
            order.last_digit = notification_data.get('MaskedPan')[-4:]
            order.auth_code = notification_data.get('AuthCode')
            order.tran_type = notification_data.get('trantype')
            order.card_brand = notification_data.get('EXTRA.CARDBRAND')
            order.isPayedbyTetraPay = True
            order._create_invoices()
            # order.send_success_mail(invoice, self)
            order._send_order_confirmation_mail()
            self.is_post_processed = True
            self.env.cr.commit()
            _logger.info("_set_done:: %s" % pprint.pformat(self.state))
            _logger.info("_set_sale:: %s" % pprint.pformat(order.state))
        else:
            self._set_error()
            self.is_post_processed = True
            self.env.cr.commit()
            _logger.info("_set_pending:: %s" % pprint.pformat(self.state))
            _logger.info(
                "Received data with invalid payment status (%s) for transaction with reference %s",
                status, self.reference,
            )

    def escapeHashValue(self, value):
        return value.replace('|', '\\|').replace('\\', '\\\\')

    def _generate_hash(self, rendering_values, tpay_storekey):
        sorted_keys = sorted(rendering_values.keys())
        hashing_values = ""

        for key in sorted_keys:
            if key.lower() not in ['encoding', 'api_url', 'hash']:
                hashing_values += self.escapeHashValue(str(rendering_values[key])) + "|"

        if tpay_storekey != None:
            storekey = self.escapeHashValue(tpay_storekey)
            hashing_values += storekey
            print("Hashing values: " + hashing_values)
            _logger.info("_Hashing values: %s" % pprint.pformat(hashing_values))

        return base64.b64encode(binascii.unhexlify(hashlib.sha512(hashing_values.encode()).hexdigest())).decode()

    def _generate_hash_response(self, rendering_values, tpay_storekey):

        sorted_keys_dict = dict((k.lower(), v) for k, v in rendering_values.items())

        sorted_keys = sorted(sorted_keys_dict.keys())

        hashing_values_arr = []
        hashing_keys = []

        for key in sorted_keys:
            if key not in ['encoding', 'hash', 'countdown']:
                hashing_values_arr.append(self.escapeHashValue(str(sorted_keys_dict[key])))
                hashing_keys.append(key.lower())

        storekey = self.escapeHashValue(tpay_storekey)
        hashing_values_arr.append(self.escapeHashValue(storekey))
        hashing_keys.append("storekey")

        hashing_values = "|".join(hashing_values_arr)
        hashing_keys_str = "|".join(hashing_keys)

        _logger.info("hashing_keys:: %s", hashing_keys_str)

        sha = hashlib.sha512()
        hashbytes = hashing_values.encode(rendering_values.get("encoding"))
        sha.update(hashbytes)
        generated_signature = base64.b64encode(sha.digest()).decode()

        _logger.info("hash_vals:: %s", hashing_values)
        _logger.info("generated_signature:: %s", generated_signature)
        _logger.info("received_signature:: %s", rendering_values.get("HASH"))

        return generated_signature
