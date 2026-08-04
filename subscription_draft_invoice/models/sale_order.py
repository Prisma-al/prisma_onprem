# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _keep_subscription_invoices_draft(self):
        # marrim vleren e parametrit qe kemmi kriju per ti kthy inv ne draft
        return self.env['ir.config_parameter'].sudo().get_param(
            'sale_subscription.keep_invoices_draft', False
        ) in ('True', 'true', '1', True)

    def _process_auto_invoice(self, invoice):
       # bejme override kt funksionin ne baze te funksionit tone kur marri paramterin
       # else do behet post si normalisht sic eshte rrjedha logjike e ktij funksioni
        if self._keep_subscription_invoices_draft():
            return
        return super()._process_auto_invoice(invoice)

    def _get_subscription_payment_exception_condition(self):
        # ky funksion heq flagun te te gjithe faturat draft qe te kaloj te croni per tu bo post
        if self._keep_subscription_invoices_draft() and not self.payment_token_id:
            return True
        return super()._get_subscription_payment_exception_condition()
