from odoo import api, fields, models


class ResPartnerExtension(models.Model):
    _inherit = ['res.partner']

    profisc_customer_vat_type = fields.Selection([
        ('ID', 'ID'),
        ('9923', 'NUIS'),
        ('VAT', 'VAT '),
    ], string='Customer Vat Type', default='ID')


    def get_tax_payer(self):
        self.env['profisc.api.helper'].getTaxPayer(self.vat)
