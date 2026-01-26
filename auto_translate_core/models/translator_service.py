# -*- coding: utf-8 -*-

from odoo import models, api
import polib
from abc import ABC, abstractmethod
import logging
import datetime
_logger = logging.getLogger(__name__)


class AutoTranslateService(models.AbstractModel):
    _name = 'auto.translate.service'
    _description = 'Auto Translate Service'

    @api.model
    def get_translator(self, service_name=None):
        # Load the default translation service from configuration if none is provided
        if service_name is None:
            service_name = self.env['ir.config_parameter'].sudo().get_param(
                'auto_translate_core.default_translation_service', 'google')
        if service_name == 'google':
            return self.env['auto.translate.google.service']
        raise ValueError(f"Unsupported translation service: {service_name}")

    @abstractmethod
    def translate_po_content(self, content, target_lang):
        pass


class GoogleAutoTranslateService(models.AbstractModel):
    _name = 'auto.translate.google.service'
    _inherit = 'auto.translate.service'
    _description = 'Google Auto Translate Service'

    @api.model
    def _get_google_translate_language(self, odoo_lang_code):
        lang_mapping = {
            'ar_001': 'ar',
            'en_GB': 'en',
            'pt_BR': 'pt',
            'zh_CN': 'zh-cn',
            'zh_TW': 'zh-tw',
        }
        base_lang = odoo_lang_code.split('_')[0]
        return lang_mapping.get(odoo_lang_code, base_lang)

    def translate_po_content(self, content, target_lang, override=False):
        from deep_translator import GoogleTranslator

        if target_lang == '__new__':
            return content

        google_lang = target_lang if target_lang in GoogleTranslator().get_supported_languages(
            as_dict=True).values() else self._get_google_translate_language(target_lang)
        _logger.info(
            f"Starting PO translation. Odoo lang: {target_lang}, Google lang: {google_lang}")

        try:
            po = polib.pofile(content.decode('utf-8'))
        except Exception as e:
            _logger.error(f"Error decoding PO file content: {str(e)}")
            return content

        translator = GoogleTranslator(source='auto', target=google_lang)
        for entry in po:
            if not entry.msgstr or override:
                try:
                    entry.msgstr = translator.translate(entry.msgid)
                except Exception as e:
                    _logger.error(
                        f"Translation error for '{entry.msgid}': {str(e)}")

        po.metadata.update({
            'X-Generator': 'Odoo Auto Translate Core',
            'PO-Revision-Date': datetime.datetime.now().strftime("%Y-%m-%d %H:%M%z")
        })

        _logger.info("PO translation completed.")
        return str(po).encode('utf-8')
