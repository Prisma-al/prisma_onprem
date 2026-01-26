{
    'name': 'Auto Translate Core',
    'version': '1.0',
    'category': 'Localization',
    'summary': 'Core translation services',
    'description': """
        This module provides core functionality for automatic translation services.
    """,
    'author': 'Odoo How',
    'website': 'https://www.yourwebsite.com',
    'depends': ['base'],
    'data': [
    ],
    'external_dependencies': {
        'python': ['polib', 'deep_translator'],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
}
