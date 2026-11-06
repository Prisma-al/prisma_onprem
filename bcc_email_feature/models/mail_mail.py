from odoo import Command, api, models


class MailMail(models.Model):
    _inherit = "mail.mail"

    @api.model
    def _create_bcc_copies(self, sources, partners):
        partners = partners.filtered("email")
        if not sources or not partners:
            return self.browse()
        copies = self.sudo().create([{
            "subject": source.subject,
            "body_html": getattr(source, "body_html", False) or source.body,
            "email_from": source.email_from,
            "reply_to": source.reply_to,
            "mail_server_id": source.mail_server_id.id,
            "scheduled_date": getattr(source, "scheduled_date", False),
            "recipient_ids": [Command.set(partners.ids)],
            "attachment_ids": [Command.set(
                source.attachment_ids.copy({"res_model": "mail.message", "res_id": 0}).ids
            )],
            "auto_delete": True,
        } for source in sources])
        self.env.ref("mail.ir_cron_mail_scheduler_action")._trigger()
        return copies
