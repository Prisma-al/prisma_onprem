# -*- coding: utf-8 -*-
import logging
import re
import pytz
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class Cx3CallLog(models.Model):
    _name = 'cx3.call.log'
    _description = '3CX Call Log'
    _order = 'call_date desc'

    # Vetem telefonatat drejtuar ketyre agjenteve behen ticket.
    TICKET_AGENTS = ('200', '203')
    # Numrat me kaq shifra ose me pak jane extension te brendshem 3CX.
    MAX_EXTENSION_DIGITS = 4
    # Timezone e paracaktuar nese kompania nuk ka nje te tille.
    DEFAULT_TIMEZONE = 'Europe/Tirane'

    name = fields.Char(string='Call Reference', readonly=True, default='New')
    caller_number = fields.Char(string='Caller Number', required=True)
    caller_name = fields.Char(string='Caller Name')
    agent = fields.Char(string='Agent')
    call_type = fields.Selection([
        ('Inbound', 'Inbound'),
        ('Outbound', 'Outbound'),
        ('Missed', 'Missed'),
        ('Notanswered', 'Not Answered'),
    ], string='Call Type', default='Inbound')
    duration = fields.Char(string='Duration')
    call_date = fields.Datetime(string='Call Date', default=fields.Datetime.now)
    description = fields.Text(string='Description')
    transcription = fields.Text(string='Transcription')
    partner_id = fields.Many2one('res.partner', string='Contact')
    ticket_id = fields.Many2one('helpdesk.ticket', string='Helpdesk Ticket')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('cx3.call.log') or 'New'
            if vals.get('caller_number') and not vals.get('partner_id'):
                partner = self._find_partner_by_phone(vals['caller_number'])
                if partner:
                    vals['partner_id'] = partner.id
                    if not vals.get('caller_name'):
                        vals['caller_name'] = partner.name
        return super().create(vals_list)

    @api.model
    def _normalize_phone(self, phone):
        """Strip all non-digit characters for comparison."""
        if not phone:
            return ''
        return re.sub(r'\D', '', phone)

    @api.model
    def _find_partner_by_phone(self, phone):
        """Find a res.partner by phone number."""
        if not phone:
            return False
        normalized = self._normalize_phone(phone)
        if not normalized:
            return False
        # Check which phone fields exist on res.partner
        partner_model = self.env['res.partner']
        phone_fields = [f for f in ['phone', 'mobile'] if f in partner_model._fields]
        if not phone_fields:
            return False
        # Build domain for partners that have a phone set
        domain = ['|'] * (len(phone_fields) - 1) + [(f, '!=', False) for f in phone_fields]
        partners = partner_model.search(domain, limit=500)
        for p in partners:
            for field in phone_fields:
                val = getattr(p, field, False)
                if val and self._normalize_phone(val) == normalized:
                    return p
            # Also try matching last digits (international prefix variations)
            if len(normalized) >= 6:
                for field in phone_fields:
                    val = getattr(p, field, False)
                    if val and self._normalize_phone(val).endswith(normalized[-9:]):
                        return p
        return False

    def _is_outgoing(self):
        """Detect outgoing calls, including unanswered ones.

        3CX reports an unanswered outgoing call as 'Notanswered', the same value
        it uses for an unanswered inbound call, so for that case the direction is
        only visible in the journal text 3CX sends as the description
        ("Unanswered outgoing call from 133 to 0672065690").
        """
        self.ensure_one()
        if self.call_type == 'Outbound':
            return True
        text = (self.description or '').lower()
        return 'outgoing call' in text or 'outbound call' in text

    def _is_internal_number(self, number):
        """Nje extension i brendshem 3CX (p.sh. 200, 133) eshte i shkurter,
        ndersa nje numer i vertete nga jashte eshte i gjate."""
        return len(self._normalize_phone(number)) <= self.MAX_EXTENSION_DIGITS

    def _should_create_ticket(self):
        """Ticket krijohet vetem per telefonata qe vijne nga jashte 3CX
        dhe qe i drejtohen agjenteve 200 ose 203."""
        self.ensure_one()
        if self._is_outgoing():
            return False
        # Telefonatat brenda 3CX (extension -> extension) nuk behen ticket.
        if self._is_internal_number(self.caller_number):
            return False
        # Vetem agjentet e caktuar.
        return (self.agent or '').strip() in self.TICKET_AGENTS

    def _create_helpdesk_ticket(self):
        """Create a helpdesk ticket from this call log entry."""
        self.ensure_one()
        team = self.env['helpdesk.team'].search([('name', '=', 'ProFisc')], limit=1)
        if not team:
            team = self.env['helpdesk.team'].search([('name', '=', 'General')], limit=1)
        priority = '2' if self.call_type in ('Missed', 'Notanswered') else '0'

        subject = "3CX Call"
        if self.caller_name:
            subject = f"Call from {self.caller_name}"
        elif self.caller_number:
            subject = f"Call from {self.caller_number}"
        if self.call_type in ('Missed', 'Notanswered'):
            subject = f"Missed call from {self.caller_name or self.caller_number}"

        body_parts = []
        if self.caller_number:
            body_parts.append(f"<b>Phone:</b> {self.caller_number}")
        if self.agent:
            body_parts.append(f"<b>Agent:</b> {self.agent}")
        if self.call_type:
            body_parts.append(f"<b>Type:</b> {self.call_type}")
        if self.duration:
            body_parts.append(f"<b>Duration:</b> {self.duration}")
        if self.description:
            body_parts.append(f"<b>Notes:</b> {self.description}")
        if self.transcription:
            body_parts.append(f"<br/><b>Transcript:</b><br/>{self.transcription}")

        body = '<br/>'.join(body_parts)

        # Nese sot kemi marre nje telefonate tjeter nga i njejti numer, nuk krijojme
        # ticket te ri por e shtojme informacionin te ticket-i ekzistues.
        ticket = self._find_todays_ticket()
        if ticket:
            ticket.description = f"{ticket.description or ''}<hr/><b>{subject}</b><br/>{body}"
            self.ticket_id = ticket.id
            _logger.info("3CX: Added call %s to existing ticket %s", self.name, ticket.name)
            return ticket

        ticket = self.env['helpdesk.ticket'].create({
            'name': subject,
            'partner_id': self.partner_id.id if self.partner_id else False,
            'team_id': team.id if team else False,
            'priority': priority,
            'description': body,
        })
        self.ticket_id = ticket.id
        _logger.info("3CX: Created helpdesk ticket %s for call %s", ticket.name, self.name)
        return ticket

    def _local_date(self, timestamp):
        if not timestamp:
            return False
        tz_name = self.env.user.tz or self.env.company.partner_id.tz or self.DEFAULT_TIMEZONE
        tz = pytz.timezone(tz_name)
        return pytz.utc.localize(timestamp).astimezone(tz).date()

    def _find_todays_ticket(self):
        """Shohim mos ka ndonje rekord me te njejtin numer"""
        self.ensure_one()
        if not self.caller_number:
            return False

        previous_call = self.search([
            ('id', '!=', self.id),
            ('caller_number', '=', self.caller_number),
            ('ticket_id', '!=', False),
        ], order='call_date desc', limit=1)
        if not previous_call:
            return False

        # A ishte ajo telefonate ne te njejten dite me kete?
        if self._local_date(previous_call.call_date) != self._local_date(self.call_date):
            return False

        # Nese ticket-i eshte mbyllur, hapim nje te ri.
        ticket = previous_call.ticket_id
        if ticket.stage_id.fold:
            return False
        return ticket
