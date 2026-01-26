from odoo import models, fields


class PosConfig(models.Model):
    _inherit = 'pos.config'

    tcr_code = fields.Selection(selection='_get_tcr_list', string='TCR')
    bu_code = fields.Selection(selection='_get_business_units', string='Business Unit')

    def _get_business_units(self):
        bus = self.env['profisc.business_units'].search([('company_id', '=', self.env.company.id)])
        return [(bu.code, bu.code) for bu in bus]

    def _get_tcr_list(self):
        bus = self.env['profisc.tcr'].search([('company_id', '=', self.env.company.id)])
        return [(bu.code, bu.code) for bu in bus]
