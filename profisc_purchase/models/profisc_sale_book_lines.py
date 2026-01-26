import logging
from odoo import api, fields, _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class ProfiscSaleBookLine(models.Model):
    _name = 'profisc.sale_book.lines'
    _description = 'List of sale Book Items that are imported from Profisc'

    book_id = fields.Many2one('profisc.sale_book', string='Sale Book')

    itemName = fields.Char(string='Item Name')
    itemDescription = fields.Char(string='Item Description')
    itemCode = fields.Char(string='Item Code')
    unitOfMeasure = fields.Char(string='Unit of Measure')
    itemQuantity = fields.Float(string='Item Quantity')
    unitPriceBefore = fields.Float(string='Price Before')
    vatRate = fields.Float(string='Vat Rate')
    itemAllowancePercent = fields.Integer(string=' Item Allowance Percent')
    allowanceValue = fields.Boolean(string=' Allowance Value')
    linePriceBefore = fields.Float(string=' Line Price Before')
    vatAmount = fields.Float(string=' VAT Amount')
    invoiceType = fields.Char(string='Invoice Type')
    partner_id = fields.Many2one('res.partner', string='Partner')


