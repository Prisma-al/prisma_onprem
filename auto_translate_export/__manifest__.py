{
    'name': 'Auto Translate Export',
    'version': '1.0',
    'category': 'Localization',
    'summary': 'Automatically translate PO files during export',
    'description': """
        This module enhances the PO file export process by automatically
        translating the content using translation services from Auto Translate Core.
    """,
    'author': 'Odoo How',
    'website': 'https://www.yourwebsite.com',
    'depends': ['base', 'auto_translate_core'],
    'data': [
        'wizard/language_export.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
