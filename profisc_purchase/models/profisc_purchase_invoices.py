import logging
from odoo import api, fields, _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ProfiscPurchaseInvocies(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'profisc.purchase_invoices'
    _description = 'List of purchase Invoices that are imported from Profisc. They can be modified before imported to ' \
                   'the Accounting module'

    purch_imported_date = fields.Date(string='Import date (CIS)')
    purch_doc_number = fields.Char(string='Doc Number')
    purch_iic = fields.Char(string='IIC')
    purch_fic = fields.Char(string='FIC')
    purch_eic = fields.Char(string='EIC')
    purch_nuis = fields.Char(string='NIPT')

    purch_party_type = fields.Selection([
        ('BUYER', 'Buyer'),
        ('SELLER', 'Seller')
    ], store=True, string='Party Type', default="BUYER")

    purch_supplier_odoo = fields.Char(string='Furitori (odoo)')
    purch_cis_status = fields.Char(string='Cis Status')
    purch_profile_id = fields.Selection(selection='_get_einvoice_profiles', string='Profile ID')
    purch_debit_credit_invoice = fields.Selection([("1", "Debit"), ("2", "Credit")], string='Debit/Credit invoice')
    purch_start_date = fields.Date(string='Start Date')
    purch_end_date = fields.Date(string='End Date')
    purch_tax_excluded = fields.Float(string="Tax Excluded", digits=(10, 2))
    purch_tax_value = fields.Float(string="Tax Value", digits=(10, 2))
    purch_tax_inc_value = fields.Float(string="Tax Included", digits=(10, 2))
    purch_amount = fields.Float(string="Amount", digits=(10, 2))
    purch_currency = fields.Char(string='Currency')
    purch_currency_ex_rate = fields.Float(string="Ex Rate", digits=(10, 2))
    purch_issue_date = fields.Date(string='Issue Date')
    purch_due_date = fields.Date(string='Due Date')
    purch_cor_ref_iic = fields.Char(string='IIC Ref')
    purch_cor_ref_date = fields.Date(string='Date Ref')
    purch_is_imported = fields.Boolean(string='Is Imported', default=False)
    purch_is_extracted = fields.Boolean(string='Is Extracted', default=False)
    purch_imported_bill_id = fields.Char(string='BILL/ID')
    purch_qr_url = fields.Char(string='Qr Url')
    attachment_ids = fields.One2many('ir.attachment', 'res_id',
                                     domain=[('res_model', '=', 'profisc.purchase_invoices')], string='Attachments')
    invoice_lines_ids = fields.One2many('profisc.purchase_invoice.lines', 'invoice_id', string="Invoice Lines")
    partner_id = fields.Many2one('res.partner', string='Partner')

    def _get_einvoice_profiles(self):
        bus = self.env['profisc.einvoice_profiles'].search([], order='code')
        return [(bu.code, bu.name) for bu in bus]

    def get_all_invoices(self):
        response = self.env['profisc.purchase_actions'].get_all_invoices()
        _logger.info(f"Response:{response}")

    def extractInvoice(self):
        response = self.env['profisc.purchase_actions'].extract_purchase_invoice(self.purch_eic)
        _logger.info(f"Response:{response}")

    def extract_invoices(self):
        active_ids = self._context.get('active_ids')
        if not active_ids:
            raise UserError("Nuk u gjeten fatura per ridergim")
        for purchase_id in active_ids:
            self.env['profisc.purchase_actions'].extract_purchase_invoice_by_id(purchase_id)

    def importInvoice(self):
        response = self.env['profisc.purchase_actions'].import_invoice_to_vendor()
        _logger.info(f"Response:{response}")

    def action_open_invoice_wizard(self):
        return {
            'name': _('Search Profisc'),
            'type': 'ir.actions.act_window',
            'res_model': 'profisc.invoice_wizard',
            'view_mode': 'form',
            'target': 'new',
        }
