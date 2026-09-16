import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

HELPDESK_TEAM_NAME = 'General'
CLOSED_STAGE_NAMES = ('Closed', 'Solved')


class WhatsAppMessage(models.Model):
    _inherit = 'whatsapp.message'

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            try:
                record._create_or_update_helpdesk_ticket()
            except Exception:
                _logger.exception('Error creating helpdesk ticket from WhatsApp message %s', record.id)
        return records

    def _create_or_update_helpdesk_ticket(self):
        is_incoming = self.state == 'received'
        is_outgoing_reply = self.state in ('sent', 'outgoing')

        if not is_incoming and not is_outgoing_reply:
            return

        # Skip template messages (only capture free-form replies)
        if is_outgoing_reply:
            try:
                if self.wa_template_id:
                    return
            except Exception:
                pass
            # Also skip if body looks like a template (contains template variables)
            body_text = self.body or ''
            if 'Pershendetje' in body_text and 'eshte perditesuar' in body_text:
                return

        phone = self.mobile_number or ''
        if not phone:
            return

        clean_body = self._strip_html_tags(self.body or '')
        if not clean_body:
            return

        # Find partner by phone number
        search_phone = phone[-9:]
        partner = self.env['res.partner'].search(
            [('phone', 'ilike', search_phone)], limit=1
        )
        if not partner and is_incoming:
            partner = self.env['res.partner'].sudo().create({
                'name': 'WhatsApp %s' % phone,
                'phone': phone,
            })

        if not partner:
            return

        # Find existing open ticket for this customer
        closed_stages = self.env['helpdesk.stage'].search(
            [('name', 'in', list(CLOSED_STAGE_NAMES))]
        )
        existing_ticket = self.env['helpdesk.ticket'].search([
            ('partner_id', '=', partner.id),
            ('stage_id', 'not in', closed_stages.ids),
        ], limit=1, order='create_date desc')

        sender = partner.name or phone
        if is_outgoing_reply:
            sender = 'Support'

        if not existing_ticket and is_incoming:
            self._create_ticket_from_whatsapp(partner, sender, clean_body)
        elif existing_ticket:
            self._update_ticket_from_whatsapp(existing_ticket, sender, clean_body)

    def _create_ticket_from_whatsapp(self, partner, sender, clean_body):
        team = self.env['helpdesk.team'].search(
            [('name', '=', HELPDESK_TEAM_NAME)], limit=1
        )
        ticket = self.env['helpdesk.ticket'].sudo().create({
            'name': 'WhatsApp nga %s' % (partner.name or sender),
            'team_id': team.id if team else False,
            'partner_id': partner.id,
            'description': '<p>%s: %s</p>' % (sender, clean_body),
        })
        ticket.sudo().message_post(
            body='WhatsApp nga %s: %s' % (sender, clean_body),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        _logger.info('Created helpdesk ticket #%s from WhatsApp message', ticket.id)

    def _update_ticket_from_whatsapp(self, ticket, sender, clean_body):
        # Post to chatter
        ticket.sudo().message_post(
            body='WhatsApp nga %s: %s' % (sender, clean_body),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )
        # Append to description
        old_desc = ticket.description or ''
        new_line = '<p>%s: %s</p>' % (sender, clean_body)
        if old_desc:
            ticket.sudo().write({'description': '%s%s' % (old_desc, new_line)})
        else:
            ticket.sudo().write({'description': new_line})

    @staticmethod
    def _strip_html_tags(text):
        result = []
        in_tag = False
        for char in text:
            if char == '<':
                in_tag = True
            elif char == '>':
                in_tag = False
            elif not in_tag:
                result.append(char)
        return ''.join(result).strip()
