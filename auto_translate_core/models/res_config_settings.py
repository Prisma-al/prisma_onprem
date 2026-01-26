# -*- coding: utf-8 -*-

from odoo import models, fields, api

class TranslatorConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    translation_service = fields.Selection([
        ('google', 'Google Translate')
    ], string="Default Translation Service",config_parameter='auto_translate_core.translation_service')