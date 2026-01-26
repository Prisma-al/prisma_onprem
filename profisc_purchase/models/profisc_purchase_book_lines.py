import logging
from odoo import api, fields, _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProfiscPurchaseBookLine(models.Model):
    _name = 'profisc.purchase_book.lines'
    _description = 'List of purchase Book Items that are imported from Profisc'

    book_id = fields.Many2one('profisc.purchase_book', string='Sale Book')

    itemName = fields.Char(string='Item Name')
    itemDescription = fields.Char(string='Item Description')
    itemCode = fields.Char(string='Item Code')
    unitOfMeasure = fields.Char(string='Unit of Measure')
    itemQuantity = fields.Float(string='Item Quantity')
    unitPrice = fields.Float(string='Price of Unit')
    vatRate = fields.Float(string='Vat', default=None)
    itemAllowancePercent = fields.Integer(string=' Item Allowance Percent')
    allowanceValue = fields.Boolean(string=' Allowance Value')
    total = fields.Float(string=' Line Price')
    vatAmount = fields.Float(string=' VAT Amount')
    invoiceType = fields.Char(string='Invoice Type')
    partner_id = fields.Many2one('res.partner', string='Partner')
    tax_ids = fields.Many2one('account.tax', string='Vat Rate')


