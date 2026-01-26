import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ProfiscPurchaseInvocieLines(models.Model):
    _name = 'profisc.purchase_invoice.lines'
    _description = 'List of purchase Invoice Items that are imported from Profisc'
    invoice_id = fields.Many2one('profisc.purchase_invoices', string='Purchase Invoice')

    itemName = fields.Char(string='Item Name')
    itemCode = fields.Char(string='Item Code')
    itemDesc = fields.Char(string='Item Description')
    priceAmount = fields.Char(string='Price')
    lineExtAmount = fields.Float(string="Ext Amount", digits=(10, 2))
    vatRate = fields.Float(string="Vat Rate", digits=(10, 2))
    vatCategory = fields.Char(string='Vat Category')
    vatExemptinReason = fields.Char(string='Vat Exempt Reason')
    allowance = fields.Float(string="Allowance", digits=(10, 2))
    allowanceCharge = fields.Float(string="Allowance Charge", digits=(10, 2))
    quantity = fields.Float(string="Qty", digits=(10, 2))
    unitOfMeasurement = fields.Char(string='Unit Of Measurement')
