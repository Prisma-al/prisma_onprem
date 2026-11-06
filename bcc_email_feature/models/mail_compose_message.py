from datetime import datetime

from odoo import api, fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    bcc_partner_ids = fields.Many2many(
        "res.partner",
        "mail_compose_message_bcc_partner_rel",
        "wizard_id",
        "partner_id",
        string="BCC",
        compute="_compute_bcc_partner_ids",
        readonly=False,
        store=True,
    )

    @api.depends("template_id")
    def _compute_bcc_partner_ids(self):
        for composer in self:
            composer.bcc_partner_ids = composer.template_id.bcc_partner_ids

    def _action_send_mail_comment(self, res_ids):
        messages = super()._action_send_mail_comment(res_ids)
        emailed = messages.filtered(
            lambda message: message.notification_ids.filtered(lambda n: n.notification_type == "email")
        )
        self.env["mail.mail"]._create_bcc_copies(emailed, self.bcc_partner_ids)
        return messages

    def _action_send_mail_mass_mail(self, res_ids, auto_commit=False):
        if not self.bcc_partner_ids:
            return super()._action_send_mail_mass_mail(res_ids, auto_commit=auto_commit)
        force_send = self.force_send
        self.force_send = False
        mails = super()._action_send_mail_mass_mail(res_ids, auto_commit=auto_commit)
        copies = self.env["mail.mail"]._create_bcc_copies(mails, self.bcc_partner_ids)
        if force_send:
            (mails | copies).filtered(
                lambda mail: not mail.scheduled_date or mail.scheduled_date <= datetime.utcnow()
            ).send(auto_commit=auto_commit)
        return mails
