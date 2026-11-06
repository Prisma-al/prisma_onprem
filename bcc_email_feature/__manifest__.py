{
    "name": "Bcc email Feature",
    "description": "An added bcc field to sent emails to the bcc partners (hidden from the customer hihihi)",
    "version": "19.0.1.0.0",
    "author": "Fabio",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "views/mail_template.xml",
        "views/mail_compose_message.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}