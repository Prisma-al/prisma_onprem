from odoo import models, fields, api, _
from datetime import datetime

year_list = []
for i in range(datetime.today().year - 3, datetime.today().year + 1):
    year_list.append((str(i), str(i)))


class ProfiscPurchaseWizard(models.TransientModel):
    _name = 'profisc.purchase_wizard'
    _description = 'Profisc purchase invoice wizard'

    period = fields.Char(string='From Date')

    month = fields.Selection([('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
                              ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
                              ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')],
                             string='Month', default = str(datetime.today().month))

    year = fields.Selection(year_list, string='Year', default = str(datetime.today().year))

    request_type = fields.Selection([('1', 'Get purchase invoice from profisc'), ('2', 'Update CIS status')], string='Request Type', default='1')

    result = fields.Text('Result')

    @api.onchange('month')
    def onchage_from_date(self):
        self.period = self.month + '/' +self.year
        print(self.period)
        print(self.month)

    @api.onchange('year')
    def chage_from_date(self):
        self.period = self.month + '/' + self.year
        print(self.period)
        print(self.month)

    def action_confirm_purchase(self):
        # Call your function here with the parameters
        # For example:
        print(self.period)
        if self.request_type == '1':
            result = self.env['profisc.book_actions'].get_all_purchase_books(self.period)

            self.result = result

            return {
                'name': _('Information'),
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'title': _('Information'),
                    'message': str(result) + ' fatura u importuan me sukses',
                    'fadeout': 'slow',
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'soft_reload',
                    }
                },
            }
        else:
            result = self.env['profisc.book_actions'].chechStatusPeriod(self.month, self.year)

            self.result = result

            return {
                'name': _('Information'),
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'title': _('Information'),
                    'message': str(result) + ' fatura ndryshuan status me sukses',
                    'fadeout': 'slow',
                    'next': {
                        'type': 'ir.actions.client',
                        'tag': 'soft_reload',
                    }
                },
            }