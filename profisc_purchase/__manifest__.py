# -*- coding: utf-8 -*-
{
    'auto_install': False,
    'installable': True,
    'application': True,
    'name': "Profisc Purchase",
    'summary': "Profisc Purchase",
    'description': """
                    ProFisc eshte nje program i certifikuar per fiskalizimin dhe e-faturen. Test bu_code=ao242je671, "
                   "tcr_code=ds683tq557, operator_code=cw384em859    """,
    'author': "Tetra Pro",
    'website': "https://profisc.al/",
    'category': 'Accounting/Accounting',
    'version': '1.0',
    'license': 'LGPL-3',

    'external_dependencies': {'python': ['pyqrcode', 'pypng', 'pycountry']},
    'depends': ['profisc'],
    'images': ['static/description/icon.png'],
    'data': [
        'security/ir.model.access.csv',
        'views/profisc_sale_book.xml',
        'views/profisc_purchase_book.xml',
        'views/res_company_extension.xml',
        'views/purch_account_tax_extension.xml',

    ],
    'assets': {
        'web.assets_frontend': [
            '/profisc_purchase/static/src/*/*.css',
        ],
        'web.assets_backend': [
            '/profisc_purchase/static/src/*/*.js',
            '/profisc_purchase/static/src/*/*.xml',
            '/profisc_purchase/static/src/*/*.css',
        ],
    }
}
