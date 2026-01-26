import logging
from odoo import api, fields, _, models

from datetime import datetime

from odoo.exceptions import UserError

from operator import length_hint

_logger = logging.getLogger(__name__)


class ProfiscPurchaseBook(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'profisc.purchase_book'
    _description = 'List of purchase Book that are imported from Profisc'

    purch_currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        tracking=True,
        required=True,
    )

    purch_base_currency = fields.Char(string="Base Currency")

    purch_exRate = fields.Float(string="Exchange Rate")

    book_lines_ids = fields.One2many('profisc.purchase_book.lines', 'book_id', string='Invoice Lines')

    purch_imported_date = fields.Date(string='Odoo Bill Date')
    purch_doc_number = fields.Char(string='Doc Number')
    purch_iic = fields.Char(string='IIC')
    purch_fic = fields.Char(string='FIC')
    purch_eic = fields.Char(string='EIC')
    purch_nuis = fields.Char(string='NIPT')
    purch_period = fields.Char(string='Period')

    purch_party_type = fields.Selection([
        ('BUYER', 'Buyer'),
        ('SELLER', 'Seller')
    ], store=True, string='Party Type', default="BUYER")

    purch_supplier_odoo = fields.Char(string='Furitori (odoo)')
    purch_cis_status = fields.Selection([("DELIVERED", "DELIVERED"), ("ACCEPTED", "ACCEPTED"), ("REFUSED", "REFUSED"),
                                         ("PARTIALLY_PAID", "PARTIALLY PAID"), ("PAID", "PAID"), ("OVERPAID", "OVERPAID")], string='Cis Status',
                                        deafult=None, tracking=True)
    purch_debit_credit_invoice = fields.Selection([("1", "Debit"), ("2", "Credit")], string='Debit/Credit invoice')
    purch_start_date = fields.Date(string='Start Date')
    purch_end_date = fields.Date(string='End Date')
    purch_tax_excluded = fields.Float(string="Untaxed Amount:", digits=(10, 2))
    purch_tax_value = fields.Float(string="Taxes:", digits=(10, 2))
    purch_tax_inc_value = fields.Float(string="Tax Included", digits=(10, 2))
    purch_total_in_currency = fields.Float(string="Total in Currency", digits=(10, 2))
    purch_amount = fields.Float(string="Total:", digits=(10, 2))
    purch_issue_date = fields.Date(string='Issue Date')
    purch_due_date = fields.Date(string='Due Date')
    purch_cor_ref_iic = fields.Char(string='IIC Ref')
    purch_cor_ref_date = fields.Date(string='Date Ref')
    purch_is_imported = fields.Selection([("not_imported", "Not Imported"), ("imported", "Imported")],
                                         string='Is Imported', default="not_imported", tracking=True)
    purch_is_AttachmentExtracted = fields.Boolean(string='Is Attachment Extracted', default=False, tracking=True)
    purch_imported_bill_id = fields.Char(string='BILL/ID')
    purch_qr_url = fields.Char(string='Qr Url')
    purch_fiscInvoiceNumber = fields.Char(string='UBLId')
    purch_invoiceType = fields.Char(string='Invoice Type')
    purch_paymentType = fields.Selection([("CASH", "Cash"), ("NONCASH", "Non Cash")], string='Payment Type')
    attachment_ids = fields.Many2many('ir.attachment', string='Attachments')
    partner_id = fields.Many2one('res.partner', string='Partner')
    purch_is_einvoice = fields.Boolean(string="Is E-Invoice", default=False)
    purch_is_custom = fields.Boolean(string="Is Custom", default=False)
    purch_is_onlyFisc = fields.Boolean(string="Only Fiscalization", default=False)
    purch_VendorBill_id = fields.Integer(string="Bill id", default=None)
    purch_sellerName = fields.Char(string="Vendor")
    purch_sellerNuis = fields.Char(string="Vendor Nuis")
    purch_isSupplierCreated = fields.Boolean(string="Is Supplier Created", default=False)
    purch_ublId = fields.Char(string="UblId")
    purch_seller_address = fields.Char(string="Supplier Address")
    purch_seller_town = fields.Char(string="Supplier Town")
    purch_seller_country = fields.Char(string="Supplier Country")

    purch_is_visible_Accept_Reject = fields.Boolean(compute='is_visible_Accept_Reject', string='Is Visible')
    purch_is_visible_Import = fields.Boolean(compute='is_visible_Import', string='Is Visible Import')

    company_id = fields.Many2one(
        'res.company',
        string='Company')

    @api.depends('purch_is_einvoice', 'purch_cis_status')
    def is_visible_Accept_Reject(self):
        for record in self:
            record.purch_is_visible_Accept_Reject = record.purch_is_einvoice and record.purch_cis_status == 'DELIVERED'

    @api.depends('purch_is_AttachmentExtracted', 'purch_is_einvoice')
    def is_visible_Import(self):
        for record in self:
            record.purch_is_visible_Import = record.purch_is_AttachmentExtracted or not record.purch_is_einvoice

    def get_all_purchase_books(self):
        response = self.env['profisc.book_actions'].get_all_purchase_books()
        _logger.info(f"Response:{response}")

    def action_open_invoice_wizard(self):
        return {
            'name': _('Search Profisc'),
            'type': 'ir.actions.act_window',
            'res_model': 'profisc.purchase_wizard',
            'view_mode': 'form',
            'target': 'new',
        }

    def import_bills(self):

        active_invoices = self.env['profisc.purchase_book'].browse(self._context.get('active_ids'))

        errors = self.env['profisc.book_actions'].import_bills(active_invoices)

        if length_hint(errors) > 0:
            string = ''
            for e in errors:
                string += e + ", "
            raise UserError(_("Faturat me FIC: "+ string + " jane importuar me pare"))


    def import_bills_template(self):

        active_invoices = self.env['profisc.purchase_book'].search([('id', '=', self.id)])
        self.env['profisc.book_actions'].import_bills(active_invoices)

    def accept_bill(self):

        list_eic = []
        list_eic.append(self.purch_eic)
        errors = self.env['profisc.book_actions'].accept_bills(list_eic, "ACCEPTED")

        if length_hint(errors) > 0:
            string = ''
            for e in errors:
                string += e + " ,"
            raise UserError(_("Faturat me FIC: " + string + " nuk kane ndryshuar status"))


    def reject_bill(self):

        list_eic = []
        list_eic.append(self.purch_eic)
        errors = self.env['profisc.book_actions'].accept_bills(list_eic, "REFUSED")

        if length_hint(errors) > 0:
            string = ''
            for e in errors:
                string += e + " ,"
            raise UserError(_("Faturat me FIC: " + string + " nuk kane ndryshuar status"))

    def accept_bills(self):

        list_eic = []
        string = ''
        active_invoices = self.env['profisc.purchase_book'].browse(self._context.get('active_ids'))

        for bill in active_invoices:
            if bill.purch_eic:
                list_eic.append(bill.purch_eic)
            else:
                string += bill.purch_fic + " ,"

        errors = self.env['profisc.book_actions'].accept_bills(list_eic, "ACCEPTED")

        if length_hint(errors) > 0:
            for e in errors:
                string += e + " ,"
            raise UserError(_("Faturat me FIC: " + string + " nuk kane ndryshuar status"))

    def reject_bills(self):

        list_eic = []
        string = ''
        active_invoices = self.env['profisc.purchase_book'].browse(self._context.get('active_ids'))

        for bill in active_invoices:
            if bill.purch_eic:
                list_eic.append(bill.purch_eic)
            else:
                string += bill.purch_fic + " ,"

        errors = self.env['profisc.book_actions'].accept_bills(list_eic, "REFUSED")

        if length_hint(errors) > 0:
            for e in errors:
                string += e + " ,"
            raise UserError(_("Faturat me FIC: " + string + " nuk kane ndryshuar status"))


    def open_VendorBill(self):

        return {
            'name': _("Vendor Bills"),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'context': {'create': False},
            'view_mode': 'form',
            'res_id': self.purch_VendorBill_id,
        }
    def create_supplier(self):

        partner = self.env['res.partner'].search([('vat', '=', self.purch_sellerNuis)], limit=1)

        if partner:
            self.partner_id = partner
            self.purch_isSupplierCreated = True
            self.message_post(body="Supplier Connected")

        else:
            partner = self.env['profisc.book_actions'].create_supplier(self.purch_sellerName, self.purch_sellerNuis, self.purch_seller_address, self.purch_seller_town)
            print(partner.name)
            self.partner_id = partner
            self.purch_isSupplierCreated = True
            self.message_post(body="Supplier Created")

        if self.purch_is_imported:
            bill = self.env['account.move'].search([('id', '=', self.purch_VendorBill_id)])
            bill.partner_id = partner

    def add_attachment_CisPurchase(self):

        old_obj = self.env['profisc.purchase_book'].search([('id', '=', self.id)])
        # old_obj_VendorBill = self.env['account.move'].search([('id', '=', self.purch_VendorBill_id)])

        self.env['profisc.book_actions'].add_attachments_CisPurchase(self.purch_eic, old_obj)

        # if self.purch_is_imported:
        #     self.env['profisc.actions'].add_attachments_vendorBill(self.purch_eic, old_obj_VendorBill)

    def checkSingleInvoiceStatus(self):

        self.env['profisc.book_actions'].checkSingleInvoiceStatus(self)

    def delete(self):

        active_invoices = self.env['profisc.purchase_book'].browse(self._context.get('active_ids'))
        self.env['profisc.book_actions'].deleteInvoices(active_invoices)



