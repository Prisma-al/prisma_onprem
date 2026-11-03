# -*- coding: utf-8 -*-

import logging
import pprint

from odoo import http
from odoo.http import request
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

_logger = logging.getLogger(__name__)


class RaiAcceptController(http.Controller):
    _success_url = '/payment/rai_accept/success'
    _failed_url = '/payment/rai_accept/failed'
    _cancel_url = '/payment/rai_accept/cancel'
    _webhook_url = '/payment/rai_accept/webhook'

    def _restore_session(self, tx_sudo):
        """Restore session data that may have been lost during the cross-origin redirect."""
        PaymentPostProcessing.monitor_transaction(tx_sudo)
        if tx_sudo.sale_order_ids:
            sale_order = tx_sudo.sale_order_ids[0]
            request.session['sale_last_order_id'] = sale_order.id
            request.session['__website_sale_last_tx_id'] = tx_sudo.id

    def _process_callback(self, status, **post):
        """Common callback logic for success/failed/cancel routes."""
        _logger.info("RaiAccept %s callback with data:\n%s", status, pprint.pformat(post))

        reference = post.get('reference')
        if not reference:
            _logger.error("RaiAccept: %s callback received without reference", status)
            return request.redirect('/payment/status')

        notification_data = {
            'reference': reference,
            'status': status,
        }

        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'rai_accept', notification_data,
        )

        self._restore_session(tx_sudo)

        try:
            tx_sudo._process_notification_data(notification_data)
        except Exception as e:
            _logger.error("RaiAccept: Failed to handle %s notification: %s", status, str(e))

        return request.redirect('/payment/status')

    @http.route(
        _success_url, type='http', auth='public',
        methods=['GET', 'POST'], csrf=False,
    )
    def success_process_transaction(self, **post):
        return self._process_callback('success', **post)

    @http.route(
        _failed_url, type='http', auth='public',
        methods=['GET', 'POST'], csrf=False,
    )
    def failed_process_transaction(self, **post):
        return self._process_callback('failed', **post)

    @http.route(
        _cancel_url, type='http', auth='public',
        methods=['GET', 'POST'], csrf=False,
    )
    def cancel_process_transaction(self, **post):
        return self._process_callback('cancel', **post)

    @http.route(
        _webhook_url, type='http', auth='public',
        methods=['POST'], csrf=False, save_session=False,
    )
    def webhook_notification(self, **post):
        import json as _json
        try:
            data = _json.loads(request.httprequest.data or '{}')
        except (ValueError, TypeError):
            data = {}
        _logger.info("RaiAccept webhook notification received:\n%s", pprint.pformat(data))

        order_id = data.get('orderIdentification', '')

        if not order_id:
            _logger.warning("RaiAccept webhook: No orderIdentification in notification")
            return request.make_json_response({'status': 'ignored'}, status=400)

        tx_sudo = request.env['payment.transaction'].sudo().search(
            [('raiaccept_order_id', '=', order_id), ('provider_code', '=', 'rai_accept')],
            limit=1,
        )

        if not tx_sudo:
            _logger.warning("RaiAccept webhook: No transaction found for order %s", order_id)
            return request.make_json_response({'status': 'not_found'}, status=404)

        # Determine status from webhook data
        status = data.get('status', '')
        if status in ('PAID', 'SUCCESS'):
            notification_status = 'success'
        elif status in ('CANCELED', 'ABANDONED'):
            notification_status = 'cancel'
        else:
            notification_status = 'failed'

        notification_data = {
            'reference': tx_sudo.reference,
            'status': notification_status,
        }

        try:
            tx_sudo._process_notification_data(notification_data)
        except Exception as e:
            _logger.error("RaiAccept webhook: Failed to process notification: %s", str(e))

        return request.make_json_response({'status': 'ok'})
