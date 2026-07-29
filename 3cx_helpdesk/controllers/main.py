# -*- coding: utf-8 -*-
import json
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class Cx3Controller(http.Controller):

    def _check_api_key(self, api_key):
        """Validate API key against Odoo user API keys."""
        if not api_key:
            return False
        user = request.env['res.users'].sudo().search([
            ('api_key_ids.scope', '=', '3cx'),
        ], limit=1)
        # Fallback: check ir.config_parameter for a simple key
        configured_key = request.env['ir.config_parameter'].sudo().get_param('3cx_helpdesk.api_key', '')
        if configured_key and api_key == configured_key:
            return True
        return False

    def _json_response(self, data, status=200):
        return Response(
            json.dumps(data, default=str),
            content_type='application/json',
            status=status,
        )

    # ─── 1. Caller Lookup ────────────────────────────────────────────────
    @http.route('/api/3cx/lookup', type='http', auth='public', methods=['GET'], csrf=False)
    def lookup(self, **kwargs):
        """
        GET /api/3cx/lookup?phone=[Number]&api_key=[key]
        Returns contact info for 3CX caller ID popup.
        """
        phone = kwargs.get('phone', '')
        api_key = kwargs.get('api_key', '')

        _logger.info("3CX Lookup request: phone=%s", phone)

        if not phone:
            return self._json_response([], status=200)

        # Authenticate
        configured_key = request.env['ir.config_parameter'].sudo().get_param('3cx_helpdesk.api_key', '')
        if configured_key and api_key != configured_key:
            return self._json_response({'error': 'Invalid API key'}, status=401)

        CallLog = request.env['cx3.call.log'].sudo()
        partner = CallLog._find_partner_by_phone(phone)

        if partner:
            result = [{
                'id': partner.id,
                'name': partner.name or '',
                'email': partner.email or '',
                'phone': partner.phone or '',
                'mobile': getattr(partner, 'mobile', '') or '',
                'company': partner.parent_id.name if partner.parent_id else (partner.company_name or ''),
            }]
            _logger.info("3CX Lookup found: %s for %s", partner.name, phone)
            return self._json_response(result)

        _logger.info("3CX Lookup: no contact found for %s", phone)
        return self._json_response([])

    # ─── 2. Report Call ──────────────────────────────────────────────────
    @http.route('/api/3cx/report-call', type='http', auth='public', methods=['POST'], csrf=False)
    def report_call(self, **kwargs):
        """
        POST /api/3cx/report-call
        Receives call data from 3CX and creates a helpdesk ticket.
        Body (JSON or form): caller, agent, call_type, duration, description, transcription
        """
        # Parse JSON body or form data
        try:
            if request.httprequest.content_type and 'json' in request.httprequest.content_type:
                data = json.loads(request.httprequest.data)
            else:
                data = kwargs
        except Exception:
            data = kwargs

        caller = data.get('caller', data.get('CallerId', ''))
        agent = data.get('agent', data.get('Agent', ''))
        call_type = data.get('call_type', data.get('CallType', 'Inbound'))
        duration = data.get('duration', data.get('Duration', ''))
        description = data.get('description', data.get('Description', ''))
        transcription = data.get('transcription', data.get('Transcription', ''))
        api_key = data.get('api_key', data.get('ApiKey', kwargs.get('api_key', '')))

        _logger.info("3CX Report Call: caller=%s, type=%s, agent=%s", caller, call_type, agent)

        # Authenticate
        configured_key = request.env['ir.config_parameter'].sudo().get_param('3cx_helpdesk.api_key', '')
        if configured_key and api_key != configured_key:
            return self._json_response({'error': 'Invalid API key'}, status=401)

        CallLog = request.env['cx3.call.log'].sudo()

        log_vals = {
            'caller_number': caller,
            'agent': agent,
            'call_type': call_type if call_type in ('Inbound', 'Outbound', 'Missed', 'Notanswered') else 'Inbound',
            'duration': duration,
            'description': description,
            'transcription': transcription,
        }

        call_log = CallLog.create(log_vals)
        if log_vals['call_type'] != 'Outbound':
            ticket = call_log._create_helpdesk_ticket()
        else:
            ticket = False

        return self._json_response({
            'success': True,
            'call_log_id': call_log.id,
            'ticket_id': ticket.id if ticket else False,
            'ticket_name': ticket.name if ticket else False,
        })

    # ─── 3. Transcript Update ────────────────────────────────────────────
    @http.route('/api/3cx/transcript', type='http', auth='public', methods=['POST'], csrf=False)
    def transcript(self, **kwargs):
        """
        POST /api/3cx/transcript
        Receives transcript after call, updates existing ticket description.
        Body (JSON or form): call_log_id or caller, transcription
        """
        try:
            if request.httprequest.content_type and 'json' in request.httprequest.content_type:
                data = json.loads(request.httprequest.data)
            else:
                data = kwargs
        except Exception:
            data = kwargs

        call_log_id = data.get('call_log_id', '')
        caller = data.get('caller', data.get('CallerId', ''))
        transcription = data.get('transcription', data.get('Transcription', ''))
        api_key = data.get('api_key', data.get('ApiKey', kwargs.get('api_key', '')))

        _logger.info("3CX Transcript update: call_log_id=%s, caller=%s", call_log_id, caller)

        if not transcription:
            return self._json_response({'error': 'No transcription provided'}, status=400)

        # Authenticate
        configured_key = request.env['ir.config_parameter'].sudo().get_param('3cx_helpdesk.api_key', '')
        if configured_key and api_key != configured_key:
            return self._json_response({'error': 'Invalid API key'}, status=401)

        CallLog = request.env['cx3.call.log'].sudo()
        call_log = False

        # Find by call_log_id first
        if call_log_id:
            call_log = CallLog.browse(int(call_log_id)).exists()

        # Fallback: find most recent call from this caller
        if not call_log and caller:
            call_log = CallLog.search([
                ('caller_number', '=', caller),
            ], order='call_date desc', limit=1)

        if not call_log:
            return self._json_response({'error': 'Call log not found'}, status=404)

        # Update call log transcription
        call_log.transcription = transcription

        # Update linked helpdesk ticket
        if call_log.ticket_id:
            existing_desc = call_log.ticket_id.description or ''
            transcript_html = f"<br/><br/><b>Transcript:</b><br/>{transcription}"
            call_log.ticket_id.description = existing_desc + transcript_html
            _logger.info("3CX: Updated ticket %s with transcript", call_log.ticket_id.name)

        return self._json_response({
            'success': True,
            'call_log_id': call_log.id,
            'ticket_id': call_log.ticket_id.id if call_log.ticket_id else False,
        })
