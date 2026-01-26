# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by MaxVueTech
# See LICENSE file for full copyright and licensing details.

""" This file manages all the operations and the functionality of the gateway
integration """

import logging

import requests

from odoo.addons.tetra_pay.const import SUPPORTED_CURRENCIES
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

globvar = 0

urls = {
    'enabled': {
        'tpay_3d_gate_url': 'https://pgw.bkt.com.al/fim/est3Dgate',
        'tpay_api_endpoint': 'https://pgw.bkt.com.al/fim/api',
    },
    'demo': {
        'tpay_3d_gate_url': 'https://entegrasyon.asseco-see.com.tr/fim/est3Dgate',
        'tpay_api_endpoint': 'https://entegrasyon.asseco-see.com.tr/fim/api',
    }
}

class AcquirerTpay(models.Model):
    """ Class to handle all the functions required in integration """
    _inherit = 'payment.provider'
    code = fields.Selection(selection_add=[('tetra_pay', 'Tetra Pay')], ondelete={'tetra_pay': 'set default'})

    tpay_clientid = fields.Char('Client Id', required_if_provider='tetra_pay', default="520000232")
    tpay_storekey = fields.Char('Store Key', required_if_provider='tetra_pay', default="SKEY1321")

    tpay_ok_url = fields.Char("Success url Callback", required_if_provider='tetra_pay',
                              default="https://stage.tetrapro.al/payment/tetra_pay/success")
    tpay_fail_url = fields.Char("Fail url Callback", required_if_provider='tetra_pay',
                                default="https://stage.tetrapro.al/payment/tetra_pay/failed")

    tpay_trantype = fields.Char("Trantype", required_if_provider='tetra_pay', default="Auth")
    tpay_refreshtime = fields.Char("Refresh time", required_if_provider='tetra_pay', default="3")

    tpay_currency = fields.Selection([
        ('008', 'ALL'),
        ('978', 'EUR'),
        ('840', 'USD'),
    ], string='Currency', required_if_provider='tetra_pay', default='008')

    tpay_lang = fields.Selection([
        ('sq', 'Albanian'),
        ('en', 'English')
    ], string='Language', required_if_provider='tetra_pay', default='en')

    tpay_encoding = fields.Selection([
        ('utf-8', 'utf-8'),
        ('ISO-8859-9', 'ISO-8859-9'),
    ], string='Encoding', required_if_provider='tetra_pay', default='ISO-8859-9')

    tpay_hash_algorithm = fields.Selection([
        ('ver1', 'V1'),
        ('ver2', 'V2'),
        ('ver3', 'V3'),
    ], string='Hash Algorithm', required_if_provider='tetra_pay', default='ver3')

    tpay_storetype = fields.Selection([
        ('pay_hosting', 'pay_hosting'),
        ('3d_pay', '3d_pay'),
        ('3d_pay_hosting', '3d_pay_hosting'),
        ('3d', '3d'),
    ], string='Store Type', required_if_provider='tetra_pay', default='3d_pay_hosting')

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, is_validation=False, **kwargs):
        """ Override of payment to filter out Flutterwave providers for unsupported currencies or
        for validation operations. """
        providers = super()._get_compatible_providers(
            *args, currency_id=currency_id, is_validation=is_validation, **kwargs
        )

        currency = self.env['res.currency'].browse(currency_id).exists()
        if (currency and currency.name not in SUPPORTED_CURRENCIES) or is_validation:
            providers = providers.filtered(lambda p: p.code != 'tetra_pay')

        return providers

    @api.model
    def _get_tpay_urls(self):
        """ tpay URLS """
        return urls.get(self.state, urls.get('demo'))


    def tpay_payment_form_generate_values(self, values):
        params = {
            'clientid': self.tpay_clientid,
            'storekey': self.tpay_storekey,
            'storetype': self.tpay_storetype

        }
        return params

    @api.model
    def _get_mygateway_form_action_url(self):
        return self._get_tpay_urls()['tpay_3d_gate_url']

    def _get_mygateway_form_generate_values(self, values):
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        mygateway_tx_values = dict(values,
                                   amount=values.get('amount'),
                                   currency=values.get('currency').name if values.get('currency') else '',
                                   return_url='%s/payment/mygateway/return' % base_url,
                                   customer_email=values.get('partner_email'),
                                   customer_id=values.get('partner_id'),
                                   reference=values.get('reference'),
                                   form_action_url=self._get_mygateway_form_action_url()
                                   )
        # If your gateway requires a signature or checksum, calculate it here and add to mygateway_tx_values
        return mygateway_tx_values

    def tpay_make_request(self, endpoint, payload=None, method='POST'):
        """ Make a request to Mercado Pago API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request.
        :param dict payload: The payload of the request.
        :param str method: The HTTP method of the request.
        :return The JSON-formatted content of the response.
        :rtype: dict
        :raise ValidationError: If an HTTP error occurs.
        """
        self.ensure_one()

        if method == 'GET':
            response = requests.get(endpoint)
        else:
            response = requests.post(endpoint)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                _logger.exception(
                    "Invalid API request at %s with data: testtttttttttttttttttt",
                )
                response_content = response.json()
                error_code = response_content.get('error')
                error_message = response_content.get('message')
                raise ValidationError("Tetra Pay: " + _(
                    "Form posting failed"
                    "information: '%s' (code %s)", error_message, error_code
                ))

        return response.json()
