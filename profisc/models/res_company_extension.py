from odoo import api, fields, models
from odoo.exceptions import UserError


class ResCompanyExtension(models.Model):
    _inherit = 'res.company'

    profisc_company_id = fields.Char("Company id", default="1", tracking=True)
    profisc_login_endpoint = fields.Char("Login endpoint", default="/public/authenticate", tracking=True)
    profisc_username = fields.Char("Username", default="bsholla", tracking=True)
    profisc_password = fields.Char("Password", default="Test1235?!", tracking=True)
    profisc_search_endpoint = fields.Char("Search endpoint", default="/apiEndpoint/search", tracking=True)
    profisc_upload_invoice = fields.Char("Upload invoice", default="/agent/upload/invoice/V2", tracking=True)
    profisc_upload_wtn_invoice = fields.Char("Upload wtn invoice", default="/agent/upload/wtn", tracking=True)
    profisc_cash_deposit = fields.Char("Register Cash Deposit", default="/agent/cashDeposit", tracking=True)
    profisc_login_token = fields.Char("Login token", default="", tracking=True)
    profisc_auto_subseq = fields.Boolean(string='Auto subseq', default=False, tracking=True)
    profisc_manual_fisc_select = fields.Boolean(string='Manual fisc select', default=False, tracking=True)
    profisc_invoiceStatus = fields.Char("Status Change Api", default="/endpoint/v2/changePurchaseInvoicesStatusInGroup", tracking=True)
    profisc_checkStatus = fields.Char("Check Status Api", default="/apiEndpoint/search", tracking=True)

    profisc_api_endpoint = fields.Selection([
        ('https://demoapi.profisc.al', 'demo'),
        ('https://online.profisc.al:8443/e-invoice-0.0.1', 'online'),
        ('https://api.profisc.al', 'portal'),
    ], string='Server', default='https://demoapi.profisc.al', tracking=True)

    profisc_purch_inv_check_time_s = fields.Integer(string='Check for new Invoices time(s)', default=3600, tracking=True)

    def get_current_company(self):
        res = self.env['profisc.actions'].getTaxPayer(self.vat)
        raise UserError(f"Current Company::{res['content'][0]}")
