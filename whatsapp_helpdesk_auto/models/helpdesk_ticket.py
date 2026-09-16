from odoo import models, fields, api


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    wa_portal_url_path = fields.Char(
        string='WhatsApp Portal URL Path',
    )

    @api.model_create_multi
    def create(self, vals_list):
        tickets = super().create(vals_list)
        for ticket in tickets:
            ticket._portal_ensure_token()
            ticket.sudo().write({
                'wa_portal_url_path': 'my/tickets/%s?access_token=%s' % (
                    ticket.id, ticket.access_token
                ),
            })
        return tickets
