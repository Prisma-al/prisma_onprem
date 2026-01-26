from odoo import models, fields, api


class ProfiscInvoiceWizard(models.TransientModel):
    _name = 'profisc.invoice_wizard'
    _description = 'Profisc purchase invoice wizard'

    from_date = fields.Date(string='From Date', required=True)

    result = fields.Text('Result')

    def action_confirm_sale(self):
        # Call your function here with the parameters
        # For example:
        result = self.env['profisc.book_actions'].get_all_sale_books(self.from_date)

        self.result = result

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


