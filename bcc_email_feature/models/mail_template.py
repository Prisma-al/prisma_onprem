from odoo import fields, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    bcc_partner_ids = fields.Many2many(
        "res.partner",
        "mail_template_bcc_partner_rel",
        "template_id",
        "partner_id",
        string="BCC",
        help="These partners receive a separate copy of every email sent with this template.",
    )

    def send_mail_batch(self, res_ids, force_send=False, raise_exception=False, email_values=None,
                        email_layout_xmlid=False):
        mails = super().send_mail_batch(
            res_ids, force_send=False, raise_exception=raise_exception,
            email_values=email_values, email_layout_xmlid=email_layout_xmlid,
        )
        copies = self.env["mail.mail"]._create_bcc_copies(mails, self.bcc_partner_ids)
        if force_send:
            (mails | copies).send(raise_exception=raise_exception)
        return mails
