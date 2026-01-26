from odoo import api, fields, models
from odoo.exceptions import UserError


class PurchaseResCompanyExtension(models.Model):
    _inherit = ['res.company']

    prof_pu_param1 = fields.Boolean(string='Import Items to Odoo Taxes', default=True,
                                    help='This option allows mapping purchase items to odoo items through TAX type.')
    prof_pu_param2 = fields.Boolean(string='Convert Qty to PCs', default=True,
                                    help="This parameter allows converting of different UOM to a standart UOM, "
                                         "for example, 30m^3 to 1 Piece")
    prof_pu_param3 = fields.Boolean(string='Group invoice products', default=True,
                                    help="This parameter allows grouping invoice items based on their respective TAX, "
                                         "for example, if there are 2 products with 20% TVSH they will be imported as "
                                         "1 product with price as price1+price2. If this option is not selected, "
                                         "each product will be imported separately, so you can change the mapping "
                                         "later for each product")
    prof_pu_param4 = fields.Boolean(string='Create supplier automatically', default=False,
                                    help="If this parameter in checked the suplier will be created automaticly in the moment bills are imported")

    @api.onchange('prof_pu_param2')
    def _onchange_boolean_field1(self):
        if self.prof_pu_param3 == False and self.prof_pu_param2 == True:
            self.prof_pu_param3 = self.prof_pu_param2