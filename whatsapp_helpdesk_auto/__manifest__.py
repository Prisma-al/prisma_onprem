{
    'name': 'WhatsApp Helpdesk Auto Ticket',
    'version': '19.0.1.0.0',
    'category': 'Services/Helpdesk',
    'summary': 'Auto-create helpdesk tickets from incoming WhatsApp messages',
    'description': """
        - Incoming WhatsApp message creates a helpdesk ticket automatically
        - Subsequent messages from same customer append to existing open ticket
        - All messages (incoming + outgoing) appear in ticket chatter and description
        - Auto-creates contact if phone number not found
        - New ticket created if previous one is closed/solved
    """,
    'author': 'Prisma',
    'website': 'https://prisma.al',
    'depends': ['whatsapp', 'helpdesk'],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
