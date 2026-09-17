import logging
from datetime import timedelta
from odoo import models, api, fields as odoo_fields

_logger = logging.getLogger(__name__)

HELPDESK_TEAM_NAME = 'General'
CLOSED_STAGE_NAMES = ('Mbyllur', 'Zgjidhur')


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
            # Also skip if body looks like a template (contains template text)
            body_text = self.body or ''
            if 'Pershendetje' in body_text and ('eshte perditesuar' in body_text or 'eshte tani ne statusin' in body_text):
                return

        phone = self.mobile_number or ''
        if not phone:
            return

        clean_body = self._strip_html_tags(self.body or '')

        # Find partner by phone number
        search_phone = phone[-9:]
        partner = self.env['res.partner'].search(
            [('phone', 'ilike', search_phone)], limit=1
        )
        if not partner and is_incoming:
            partner = self.env['res.partner'].sudo().create({
                'name': 'Klient %s' % phone,
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

        # Check for media attachments
        has_media = False
        attachment_ids = []
        try:
            # Try mail.message attachments first
            if self.mail_message_id and self.mail_message_id.attachment_ids:
                attachment_ids = self.mail_message_id.attachment_ids.ids
            # Also check attachments linked directly to this whatsapp.message
            if not attachment_ids:
                direct_atts = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'whatsapp.message'),
                    ('res_id', '=', self.id),
                ])
                if direct_atts:
                    attachment_ids = direct_atts.ids
            has_media = bool(attachment_ids)
        except Exception:
            pass

        if not clean_body and not has_media:
            return

        if not existing_ticket and is_incoming:
            self._create_ticket_from_whatsapp(partner, sender, clean_body, has_media, attachment_ids)
        elif existing_ticket:
            self._update_ticket_from_whatsapp(existing_ticket, sender, clean_body, has_media, attachment_ids)

    def _create_ticket_from_whatsapp(self, partner, sender, clean_body, has_media=False, attachment_ids=None):
        team = self.env['helpdesk.team'].search(
            [('name', '=', HELPDESK_TEAM_NAME)], limit=1
        )
        desc = '<p>%s: %s</p>' % (sender, clean_body) if clean_body else ''
        if has_media:
            desc += '<p>%s: [Media]</p>' % sender

        # Create ticket WITHOUT partner to prevent email notification
        ticket = self.env['helpdesk.ticket'].sudo().with_context(
            mail_create_nosubscribe=True,
            mail_create_nolog=True,
            tracking_disable=True,
        ).create({
            'name': 'WhatsApp nga %s' % (partner.name or sender),
            'team_id': team.id if team else False,
            'description': desc,
        })
        # Set partner after creation to avoid triggering email
        ticket.sudo().with_context(
            mail_create_nosubscribe=True,
            tracking_disable=True,
        ).write({'partner_id': partner.id})
        # Remove partner as follower to prevent any future auto-emails
        follower = self.env['mail.followers'].sudo().search([
            ('res_model', '=', 'helpdesk.ticket'),
            ('res_id', '=', ticket.id),
            ('partner_id', '=', partner.id),
        ])
        if follower:
            follower.sudo().unlink()

        # Copy attachments and build chatter message
        msg_body = 'WhatsApp nga %s: %s' % (sender, clean_body) if clean_body else ''
        new_attachment_ids = []
        if attachment_ids:
            for att in self.env['ir.attachment'].browse(attachment_ids):
                new_att = att.sudo().copy({
                    'res_model': 'helpdesk.ticket',
                    'res_id': ticket.id,
                })
                new_attachment_ids.append(new_att.id)

        if not msg_body and has_media:
            msg_body = 'WhatsApp nga %s: [Media]' % sender
        elif has_media:
            msg_body += ' [Media]'

        ticket.sudo().message_post(
            body=msg_body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            attachment_ids=new_attachment_ids or None,
        )
        _logger.info('Created helpdesk ticket #%s from WhatsApp message', ticket.id)

    def _update_ticket_from_whatsapp(self, ticket, sender, clean_body, has_media=False, attachment_ids=None):
        # Copy attachments and build message
        msg_body = 'WhatsApp nga %s: %s' % (sender, clean_body) if clean_body else ''
        new_attachment_ids = []
        if attachment_ids:
            for att in self.env['ir.attachment'].browse(attachment_ids):
                new_att = att.sudo().copy({
                    'res_model': 'helpdesk.ticket',
                    'res_id': ticket.id,
                })
                new_attachment_ids.append(new_att.id)

        if not msg_body and has_media:
            msg_body = 'WhatsApp nga %s: [Media]' % sender
        elif has_media:
            msg_body += ' [Media]'

        # Post to chatter
        ticket.sudo().message_post(
            body=msg_body,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            attachment_ids=new_attachment_ids or None,
        )
        # Append to description
        old_desc = ticket.description or ''
        new_line = '<p>%s: %s</p>' % (sender, clean_body) if clean_body else ''
        if has_media:
            new_line += '<p>%s: [Media]</p>' % sender
        if new_line:
            if old_desc:
                ticket.sudo().write({'description': '%s%s' % (old_desc, new_line)})
            else:
                ticket.sudo().write({'description': new_line})

    @api.model
    def _cron_process_whatsapp_media(self):
        """Cron job to attach media from recent WhatsApp messages to helpdesk tickets."""
        cutoff = odoo_fields.Datetime.now() - timedelta(minutes=10)
        recent_messages = self.search([
            ('create_date', '>=', cutoff),
            ('state', '=', 'received'),
        ])
        for msg in recent_messages:
            try:
                # Find attachments for this message
                attachment_ids = []
                if msg.mail_message_id and msg.mail_message_id.attachment_ids:
                    attachment_ids = msg.mail_message_id.attachment_ids.ids
                if not attachment_ids:
                    direct_atts = self.env['ir.attachment'].sudo().search([
                        ('res_model', '=', 'whatsapp.message'),
                        ('res_id', '=', msg.id),
                    ])
                    if direct_atts:
                        attachment_ids = direct_atts.ids
                if not attachment_ids:
                    continue

                # Find the partner
                phone = msg.mobile_number or ''
                if not phone:
                    continue
                search_phone = phone[-9:]
                partner = self.env['res.partner'].search(
                    [('phone', 'ilike', search_phone)], limit=1
                )
                if not partner:
                    continue

                # Find open ticket for this partner
                closed_stages = self.env['helpdesk.stage'].search(
                    [('name', 'in', list(CLOSED_STAGE_NAMES))]
                )
                ticket = self.env['helpdesk.ticket'].search([
                    ('partner_id', '=', partner.id),
                    ('stage_id', 'not in', closed_stages.ids),
                ], limit=1, order='create_date desc')
                if not ticket:
                    continue

                # Check if these attachments are already on the ticket
                existing_atts = self.env['ir.attachment'].sudo().search([
                    ('res_model', '=', 'helpdesk.ticket'),
                    ('res_id', '=', ticket.id),
                ])
                existing_names = set(existing_atts.mapped('name'))

                new_attachment_ids = []
                for att in self.env['ir.attachment'].browse(attachment_ids):
                    if att.name not in existing_names:
                        new_att = att.sudo().copy({
                            'res_model': 'helpdesk.ticket',
                            'res_id': ticket.id,
                        })
                        new_attachment_ids.append(new_att.id)

                if new_attachment_ids:
                    sender = partner.name or phone
                    ticket.sudo().message_post(
                        body='WhatsApp nga %s: [Media]' % sender,
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                        attachment_ids=new_attachment_ids,
                    )
                    _logger.info('Attached %d media files to ticket #%s via cron',
                                 len(new_attachment_ids), ticket.id)
            except Exception:
                _logger.exception('Error processing media for WhatsApp message %s', msg.id)

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
