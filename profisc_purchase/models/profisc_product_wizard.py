from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class ProfiscProductWizard(models.TransientModel):
    _name = 'profisc.product.wizard'
    _description = 'Wizard to Create New Product'

    def _create_product(self, data):
        categ_id = self._get_or_create_category()
        _logger.info(f"categ_id:{categ_id}")
        item = self.env['product.product'].create({
            'name': data['name'],
            'type': data['type'],
            'list_price': data['list_price'],
            'standard_price': data['standard_price'],
            'uom_id': 1,
            'uom_po_id': 1,
            'sale_ok': False,
            'categ_id': categ_id,
        })
        return item.id

    def _get_or_create_category(self):
        category = self.env['product.category'].search(
            [('name', '=', 'profisc_purchase')], limit=1)

        if category.id:
            return category.id

        category_vals = {
            'name': 'profisc_purchase',
        }
        category = self.env['product.category'].create(category_vals)

        return category.id

    def recreate_products(self):
        data = {
            'name': '20_pc',
            'type': 'product',
            'list_price': 100,
            'standard_price': 0,
        }
