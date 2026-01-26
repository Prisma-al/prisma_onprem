# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import base64
import logging

_logger = logging.getLogger(__name__)

class AutoTranslateLanguageExport(models.TransientModel):
    _inherit = "base.language.export"

    override_msgstr = fields.Boolean(string="Override Existing Translations", default=False,
                                     help="if checked, existing translations will be replaced by the translations from the service else"
                                          "the existing translations will be kept")

    def act_getfile(self):
        result = super(AutoTranslateLanguageExport, self).act_getfile()
        if self.format == 'po' and result['type'] == 'ir.actions.act_window':
            file_content = base64.b64decode(self.data)
            translator = self.env['auto.translate.service'].get_translator('google')
            modified_content = translator.translate_po_content(file_content, self.lang, self.override_msgstr)
            self.write({'data': base64.encodebytes(modified_content)})
        return result