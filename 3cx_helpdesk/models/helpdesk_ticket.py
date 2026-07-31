from odoo import models, fields, api

class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # fush eboolean qe kontrollon a eshte kriju ticket nga 3cx
    ticket_from_3cx = fields.Boolean(string="Is ticket from 3cx", default=False)