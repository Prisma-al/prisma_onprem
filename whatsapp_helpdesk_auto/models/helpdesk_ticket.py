from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    wa_portal_url_path = fields.Char(
        string='WhatsApp Portal URL Path',
        compute='_compute_wa_portal_url_path',
    )

    @api.depends('access_token')
    def _compute_wa_portal_url_path(self):
        for ticket in self:
            ticket._portal_ensure_token()
            ticket.wa_portal_url_path = 'my/tickets/%s?access_token=%s' % (
                ticket.id, ticket.access_token
            )
