# -*- coding: utf-8 -*-
{
    'name': 'RaiAccept Payment Provider',
    'category': 'Hidden',
    'sequence': 350,
    'summary': 'Payment Provider: RaiAccept Integration for eCommerce',
    'version': '19.0.1.0.0',
    'author': 'Prisma',
    'description': """RaiAccept Payment Gateway Integration for Odoo Website eCommerce""",
    'depends': ['payment', 'sale', 'website_sale', 'profisc'],
    'data': [
        'security/ir.model.access.csv',
        'views/payment_templates.xml',
        'views/payment_provider_views.xml',
        'data/raiaccept.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'rai_accept/static/src/js/payment_form.js',
        ],
    },
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'license': 'LGPL-3',
}