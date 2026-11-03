# -*- coding: utf-8 -*-

import json
import logging

import requests

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

RAIACCEPT_AUTH_URL = 'https://authenticate.raiaccept.com'
RAIACCEPT_API_URL = 'https://trapi.raiaccept.com'
RAIACCEPT_COGNITO_CLIENT_ID = 'kr2gs4117arvbnaperqff5dml'


class PaymentProviderRaiAccept(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('rai_accept', 'RaiAccept')],
        ondelete={'rai_accept': 'set default'},
    )

    raiaccept_username = fields.Char(
        string='API Username',
        required_if_provider='rai_accept',
        help='API username generated in the RaiAccept Merchant Portal.',
    )
    raiaccept_password = fields.Char(
        string='API Password',
        required_if_provider='rai_accept',
        help='API password generated in the RaiAccept Merchant Portal.',
    )
    raiaccept_client_id = fields.Char(
        string='Cognito Client ID',
        required_if_provider='rai_accept',
        default=RAIACCEPT_COGNITO_CLIENT_ID,
        help='AWS Cognito Client ID for RaiAccept authentication.',
    )
    raiaccept_currency = fields.Selection([
        ('ALL', 'ALL - Albanian Lek'),
        ('EUR', 'EUR - Euro'),
        ('USD', 'USD - US Dollar'),
        ('RSD', 'RSD - Serbian Dinar'),
        ('GBP', 'GBP - British Pound'),
    ], string='Currency', required_if_provider='rai_accept', default='ALL')

    def _raiaccept_authenticate(self):
        """Authenticate with RaiAccept via AWS Cognito and return the IdToken."""
        self.ensure_one()
        payload = {
            'AuthFlow': 'USER_PASSWORD_AUTH',
            'AuthParameters': {
                'USERNAME': self.raiaccept_username,
                'PASSWORD': self.raiaccept_password,
            },
            'ClientId': self.raiaccept_client_id,
        }
        headers = {
            'Content-Type': 'application/x-amz-json-1.1',
            'X-Amz-Target': 'AWSCognitoIdentityProviderService.InitiateAuth',
        }
        try:
            response = requests.post(
                RAIACCEPT_AUTH_URL,
                json=payload,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            result = response.json()
            id_token = result.get('AuthenticationResult', {}).get('IdToken')
            if not id_token:
                raise ValidationError(_("RaiAccept: Authentication failed - no token received."))
            _logger.info("RaiAccept authentication token: %s", str(id_token))
            return id_token
        except requests.exceptions.RequestException as e:
            _logger.error("RaiAccept authentication failed: %s", str(e))
            raise ValidationError(_("RaiAccept: Authentication failed - %s", str(e)))

    def _raiaccept_create_order(self, token, order_data):
        """Create an order entry in RaiAccept and return the orderIdentification."""
        self.ensure_one()
        headers = {
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(
                '%s/orders' % RAIACCEPT_API_URL,
                json=order_data,
                headers=headers,
                timeout=30,
            )
            if response.status_code >= 400:
                _logger.error(
                    "RaiAccept order creation HTTP %s — body: %s",
                    response.status_code, response.text,
                )
            response.raise_for_status()
            result = response.json()
            _logger.info("RaiAccept create order raw response: %s", json.dumps(result, indent=2))
            order_identification = result.get('orderIdentification')
            if not order_identification:
                raise ValidationError(_("RaiAccept: Order creation failed - no order ID received."))
            _logger.info("RaiAccept order created: %s", order_identification)
            return result
        except requests.exceptions.RequestException as e:
            _logger.error("RaiAccept order creation failed: %s", str(e))
            raise ValidationError(_("RaiAccept: Order creation failed - %s", str(e)))

    def _raiaccept_create_payment_session(self, token, order_identification, order_data):
        """Create a payment session and return the paymentRedirectURL."""
        self.ensure_one()
        headers = {
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(
                '%s/orders/%s/checkout' % (RAIACCEPT_API_URL, order_identification),
                json=order_data,
                headers=headers,
                timeout=30,
            )
            if response.status_code >= 400:
                _logger.error(
                    "RaiAccept checkout HTTP %s — body: %s",
                    response.status_code, response.text,
                )
            response.raise_for_status()
            result = response.json()
            payment_url = result.get('paymentRedirectURL')
            if not payment_url:
                raise ValidationError(
                    _("RaiAccept: Payment session creation failed - no redirect URL received.")
                )
            _logger.info("RaiAccept payment session created: %s", result.get('sessionId'))
            return result
        except requests.exceptions.RequestException as e:
            _logger.error("RaiAccept payment session creation failed: %s", str(e))
            raise ValidationError(_("RaiAccept: Payment session creation failed - %s", str(e)))

    def _raiaccept_get_order_status(self, token, order_identification):
        """Retrieve order details from RaiAccept to verify payment status."""
        self.ensure_one()
        headers = {
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
        }
        try:
            response = requests.get(
                '%s/orders/%s' % (RAIACCEPT_API_URL, order_identification),
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("RaiAccept order status retrieval failed: %s", str(e))
            raise ValidationError(_("RaiAccept: Failed to retrieve order status - %s", str(e)))

    def _raiaccept_get_transactions(self, token, order_identification):
        """Retrieve all transactions for an order from RaiAccept."""
        self.ensure_one()
        headers = {
            'Authorization': 'Bearer %s' % token,
            'Content-Type': 'application/json',
        }
        try:
            response = requests.post(
                '%s/orders/%s/transactions' % (RAIACCEPT_API_URL, order_identification),
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error("RaiAccept transactions retrieval failed: %s", str(e))
            return None
