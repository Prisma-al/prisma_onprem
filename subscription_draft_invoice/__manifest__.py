# -*- coding: utf-8 -*-
{
    'name': 'Subscription Draft Invoices',
    'version': '19.0.1.0.0',
    'category': 'Sales/Subscriptions',
    'summary': 'Keep recurring subscription invoices in draft instead of posting them automatically',
    'description': """
        This module sets the subscription invoices to draft rather then posting them
    """,
    'author': 'Prisma',
    'website': 'https://prisma.al',
    'depends': ['sale_subscription'],
    'data': [
        'data/ir_config_parameter.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
