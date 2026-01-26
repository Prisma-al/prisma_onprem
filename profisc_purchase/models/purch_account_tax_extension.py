from odoo import api, fields, models


class AccountTaxExtension(models.Model):
    _inherit = ['account.tax']

    purch_allow_product_mapping = fields.Boolean(string='Allow product mapping')
    purch_product_id = fields.Many2one('product.product', string='Purchase Product')