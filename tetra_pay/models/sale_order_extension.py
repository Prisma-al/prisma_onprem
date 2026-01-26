from odoo import api, fields, models, _


class SaleOrderExtension(models.Model):

    _inherit = ["sale.order"]

    last_digit = fields.Char(string='Lat Digit', default=None)
    auth_code = fields.Char(string='Auth Code', default=None)
    tran_type = fields.Char(string='Tran Type', default=None)
    card_brand = fields.Char(string='Card Brand', default=None)
    isPayedbyTetraPay = fields.Boolean(string='Is payed bt Tetra Pay', default=False)
