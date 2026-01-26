# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by MaxVueTech
# See LICENSE file for full copyright and licensing details.
{
    'name': 'TetraPro Payment Acquirer',
    'category': 'Hidden',
    'sequence': 350,
    'summary': 'Payment Acquirer: TetraPro Implementation',
    'version': '2.0',
    'author': 'Bruno Sholla',
    'website': 'https://tetrapro.al',
    'description': """TetraPro Payment Acquirer""",
    'depends': ['payment', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_templates.xml',
        'views/payment_provider_views.xml',
        'data/tpay.xml',
    ],
    'license': 'LGPL-3',
    'images': [
        'static/description/tpay_payment_gateway_banner.png',
    ],
}
