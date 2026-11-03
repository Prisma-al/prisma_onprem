# -*- coding: utf-8 -*-

from odoo import fields, models


class RaiAcceptPayments(models.Model):
    _name = 'raiaccept.payments'
    _description = 'RaiAccept Payment Record'

    order_identification = fields.Char(string='Order Identification')
    transaction_id = fields.Char(string='Transaction ID')
    merchant_order_reference = fields.Char(string='Merchant Order Reference')
    amount = fields.Float(string='Amount')
    currency = fields.Char(string='Currency')
    transaction_type = fields.Char(string='Transaction Type')
    status = fields.Char(string='Order Status')
    status_code = fields.Char(string='Status Code')
    status_message = fields.Char(string='Status Message')
    payment_method = fields.Char(string='Payment Method')
    masked_card_number = fields.Char(string='Masked Card Number')
    card_type = fields.Char(string='Card Type')
    card_holder_name = fields.Char(string='Card Holder Name')
    issuer_country = fields.Char(string='Issuer Country')
    created_on = fields.Char(string='Created On')
    updated_on = fields.Char(string='Updated On')
    is_production = fields.Boolean(string='Is Production', default=False)
