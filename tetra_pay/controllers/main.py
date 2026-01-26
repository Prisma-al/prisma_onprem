# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by MaxVueTech
# See LICENSE file for full copyright and licensing details.

""" File to manage the functions used while redirection"""

import hmac
import logging
import pprint
import werkzeug
from werkzeug.exceptions import Forbidden

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class TpayController(http.Controller):
    _success_url = '/payment/tetra_pay/success'
    _failed_url = '/payment/tetra_pay/failed'

    @http.route(_success_url, type='http', auth='public', methods=['GET', 'POST'], csrf=False, save_session=False)
    def success_process_transaction(self, **post):
        _logger.info("Handling success processing with data:\n%s", pprint.pformat(post))

        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'tetra_pay', post
        )

        self._verify_notification_signature(post, tx_sudo)

        tx_sudo._handle_notification_data('tetra_pay', post)

        return request.redirect('/payment/status')

    @http.route(_failed_url, type='http', auth='public', methods=['POST'], csrf=False)
    def failed_process_transaction(self, **post):
        _logger.info("Handling failed processing with data:\n%s", pprint.pformat(post))
        pprint.pformat(post)
        return False

    @staticmethod
    def _verify_notification_signature(notification_data, tx_sudo):
        """ Check that the received signature matches the expected one.

        :param dict notification_data: The notification data
        :param recordset tx_sudo: The sudoed transaction referenced by the notification data, as a
                                  `payment.transaction` record
        :return: None
        :raise: :class:`werkzeug.exceptions.Forbidden` if the signatures don't match
        """
        # Retrieve the received signature from the data
        received_signature = notification_data.get('HASH')
        if not received_signature:
            _logger.warning("received notification with missing signature")
            raise Forbidden()

        # Compare the received signature with the expected signature computed from the data
        expected_signature = tx_sudo._generate_hash_response(notification_data, tx_sudo.provider_id.tpay_storekey)
        if not received_signature == expected_signature:
            _logger.warning("received notification with invalid signature")
            raise Forbidden()
