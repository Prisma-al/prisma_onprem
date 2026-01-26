import logging
from odoo import api, fields, _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProfiscSaleBook(models.Model):

    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'profisc.sale_book'
    _description = 'List of sale Book that are imported from Profisc'

    cisStatus = fields.Char(string='CIS')
    currency = fields.Char(string='Currency')

    book_lines_ids = fields.One2many('profisc.sale_book.lines', 'book_id', string='Book Lines')

    partner_id = fields.Many2one('res.partner', string='Partner')
    supplier_odoo = fields.Char(string='Furitori (odoo)')
    businessUnitCode = fields.Char(string='Business Unit')

    attachment_ids = fields.One2many('ir.attachment', 'res_id',
                                     domain=[('res_model', '=', 'profisc.purchase_book')], string='Attachments')

    badDebt = fields.Boolean(string='Bad Debt')
    bedDebtTaxableAmount = fields.Float(string='Bed Debt Taxable Amount')
    bedDebtTaxAmount = fields.Float(string='Bed Debt Tax Amount')
    custom = fields.Boolean(string='Custom')
    domesticPurchaseOfInvestmentTwentyPercentTaxableAmount = fields.Float(string='Domestic Purchase Taxable Amount')
    domesticPurchaseOfInvestmentTwentyPercentTaxAmount = fields.Float(string='Domestic Purchase Tax Amount')
    domesticPurchaseOfInvestmentWithoutVat = fields.Float(string='Domestic Purchase Tax Amount without VAT')
    domesticpurchaseWithSixPercentVat = fields.Boolean(string='Domestic Purchase Tax Amount with Six Percent VAT')
    domesticpurchaseWithTenPercentVat = fields.Boolean(string='Domestic Purchase Tax Amount with Ten Percent VAT')
    domesticpurchaseWithTwentyPercentVat = fields.Boolean(string='Domestic Purchase Tax Amount with Twenty Percent VAT')
    domesticPurchaseWithVat = fields.Boolean(string='Domestic Purchase')
    eic = fields.Char(string='EIC')
    einvoice = fields.Boolean(string='Einvoice')
    purch_end_date = fields.Date(string='End Date')
    exemptedFromVat = fields.Boolean(string='Exempted From Vat')
    exemptedImportGoodsAmount = fields.Float(string='Exempted Import Goods Amount')
    exemptedPurchaseAmount = fields.Float(string='Exempted Purchase Amount')
    fic = fields.Char(string='FIC')
    iic = fields.Char(string='IIC')
    # impCustDecNum =
    importExempted = fields.Boolean(string='importExempted')
    investment = fields.Boolean(string='investment')
    investmentExemptedImportGoodsAmount = fields.Float(string='Investment Exempted Import')
    investmentTwentyPercentImportGoodsTaxableAmount = fields.Float(string='Investment Twenty Percent Import')
    invoiceType = fields.Char(string='Invoice Type')
    issueDate = fields.Date(string='Issue Date')
    onlyFisc = fields.Boolean(string='Only Fisc')
    paymentType = fields.Char(string='Payment Type')
    period = fields.Char(string = 'Period')
    buyerName = fields.Char(string = 'Buyer Name')
    buyerNuis = fields.Char(string = 'buyerNuis')
    fiscInvoiceNumber = fields.Char(string = 'Fisc Invoice Number')
    purchaseFromDomesticFarmersSixPercentTaxableAmount = fields.Float(string='Purchase From Domestic Farmers Six Percent Taxable Amount')
    purchaseFromDomesticFarmersSixPercentTaxAmount = fields.Float(string='Purchase From Domestic Farmers Six Percent Tax Amount')
    purchaseFromDomesticSellersSixPercentTaxableAmount = fields.Float(string = 'Purchase From Domestic Sellers Six Percent Taxable Amount')
    purchaseFromDomesticSellersSixPercentTaxAmount = fields.Float(string = 'Purchase From Domestic Sellers Six Percent Tax Amount')
    purchaseFromDomesticSellersTenPercentTaxableAmount = fields.Float(string='Purchase From Domestic Sellers Ten Percent Taxable Amount')
    purchaseFromDomesticSellersTenPercentTaxAmount = fields.Float(string = 'Purchase From Domestic Sellers Ten Percent Tax Amount')
    purchaseFromDomesticSellersTwentyPercentTaxableAmount = fields.Float(string = 'Purchase From Domestic Sellers Twenty Percent Taxable Amount')
    purchaseFromDomesticSellersTwentyPercentTaxAmount = fields.Float(string = 'Purchase From Domestic Sellers Twenty Percent Tax Amount')
    purchaseFromFarmers = fields.Boolean(string = 'Purchase From Farmers')
    qr_url = fields.Char(string='Qr Url')
    reverseCharge = fields.Boolean(string='Reverse Charge')
    reverseChargeTaxableAmount = fields.Float(string='Reverse Charge Taxable Amount')
    reverseChargeTaxAmount = fields.Float(string='Reverse Charge Tax Amount')
    buyerCity = fields.Char(string='Seller City')
    buyerCountry = fields.Char(string='Seller Country')
    sellerNuis = fields.Char(string='Seller NUIS')
    sixPercentImportGoodsTaxableAmount = fields.Float(string = 'Six Percent Import Goods Taxable Amount')
    sixPercentImportGoodsTaxAmount = fields.Float(string = 'Six Percent Import Goods Tax Amount')
    sixPercentVatRated = fields.Float(string = 'Six Percent Vat Rated')
    standardImport = fields.Boolean(string = 'Standard Import')
    standardPurchase = fields.Boolean(string = 'Standard Purchase')
    startDate  = fields.Date(string='Start Date')
    tenPercentImportGoodsTaxableAmount = fields.Float(string = 'Ten Percent Import Goods Taxable Amount')
    tenPercentImportGoodsTaxAmount = fields.Float(string = 'Ten Percent Import Goods Tax Amount')
    tenPercentVatRated = fields.Boolean(string = 'Ten Percent Vat Rated')
    totalWithoutVat = fields.Float(string = 'total without VAT')
    salesTot = fields.Float(string = 'Total Purchase')
    twentyPercentImportGoodsTaxableAmount = fields.Float(string = 'Twenty Percent Import Goods Taxable Amount')
    twentyPercentImportGoodsTaxAmount = fields.Float(string = 'Twenty Percent Import Goods Tax Amount')
    twentyPercentVatRated = fields.Boolean(string = 'Twenty Percent Vat Rated')
    # vatTotal  = fields.Float(string = '')
    zeroVatAndExemptedPurchaseAmount = fields.Float(string = 'Zero VAT and Exempted Purchase Amount')
    zeroVatPurchaseAmount = fields.Float(string = 'Zero VAT and Purchase Amount')
    zeroVatRated = fields.Boolean(string = 'Zero VAT Rated')
    isExtracted = fields.Boolean(string = 'Extracted', default=False)

    def get_all_sale_books(self):
        response = self.env['profisc.book_actions'].get_all_sale_books()
        _logger.info(f"Response:{response}")

    def add_attachments(self):
        response = self.env['profisc.book_actions'].add_attachments()
        _logger.info(f"Response:{response}")

    def action_open_invoice_wizard(self):
        return {
            'name': _('Search Profisc'),
            'type': 'ir.actions.act_window',
            'res_model': 'profisc.invoice_wizard',
            'view_mode': 'form',
            'target': 'new',
        }