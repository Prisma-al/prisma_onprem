from odoo import api, fields, models


class ProfiscBusinessUnits(models.Model):
    _name = 'profisc.business_units'
    _description = 'List of all Business Units'

    code = fields.Char(string='Code')
    name = fields.Char(string='Name')
    address = fields.Char(string='Address')
    company_id = fields.Many2one('res.company', string='Company')
