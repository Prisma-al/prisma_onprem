# -*- coding: utf-8 -*-
{
    'name': '3CX Helpdesk Integration',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': '3CX V20 PBX integration - caller lookup, auto ticket creation, transcripts',
    'description': """
        Integrates 3CX V20 phone system with Odoo Helpdesk:
        - Caller lookup by phone number (shows caller name on 3CX client)
        - Auto-create helpdesk tickets when calls end
        - High-priority tickets for missed calls
        - Call transcript support from 3CX AI transcription
    """,
    'author': 'Prisma',
    'website': 'https://prisma.al',
    'depends': ['helpdesk', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/call_log_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
