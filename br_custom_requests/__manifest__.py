# -*- coding: utf-8 -*-
{
    'name': "rest_api_helper",

    'summary': "Enable requests library in server actions",

    'description': "Enable requests library in server actions",
    'author': "Bruno Sholla",
    'website': "https://www.tetrapro.al",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Tools',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'views/views.xml',
        'views/templates.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
