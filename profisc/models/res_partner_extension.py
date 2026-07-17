from odoo import api, fields, models


class ResPartnerExtension(models.Model):
    _inherit = ['res.partner']

    profisc_customer_vat_type = fields.Selection([
        ('ID', 'ID'),
        ('9923', 'NUIS'),
        ('VAT', 'VAT '),
    ], string='Customer Vat Type', default='ID')


    @api.model
    def _load_pos_data_fields(self, config_id):
        fields = super()._load_pos_data_fields(config_id)
        if 'profisc_customer_vat_type' not in fields:
            fields += ['profisc_customer_vat_type']
        return fields

    def get_tax_payer(self):
        self.env['profisc.api.helper'].getTaxPayer(self.vat)
