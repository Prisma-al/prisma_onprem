from odoo import api, fields, models


class ProfiscTcr(models.Model):
    _name = 'profisc.tcr'
    _description = 'List of all tcrs'

    code = fields.Char(string='Code')
    name = fields.Char(string='Name')
    bu_id = fields.Many2one('profisc.business_units', string='Business Unit')
    company_id = fields.Many2one('res.company', string='Company')
