import uuid
from odoo import models, fields


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    wa_portal_url_path = fields.Char(
        string='WhatsApp Portal URL Path',
        compute='_compute_wa_portal_url_path',
    )

    def _compute_wa_portal_url_path(self):
        for ticket in self:
            token = ticket.access_token
            if not token:
                token = str(uuid.uuid4())
                ticket.sudo().write({'access_token': token})
            ticket.wa_portal_url_path = 'my/tickets/%s?access_token=%s' % (
                ticket.id, token
            )
