import json
from odoo import api, fields, models
from odoo.exceptions import UserError

# from .functions.profisc_helper import profisc_helper
import requests


class Profisc(models.Model):
    _name = 'profisc.api.helper'
    _description = 'Profisc API'

    @api.model
    def getTaxPayer(self, nuis):
        returned_json = self.env['profisc.actions'].getTaxPayer(nuis)
        raise UserError(f"returned_json:{returned_json}")

    @api.model
    def sendToProfisc(self, account_move_id):
        self.env['profisc.actions'].sendToProfisc(account_move_id)
        # raise UserError(f"returned_json:{returned_json}")

    @api.model
    def getQrCode(self, account_move_id):
        self.env['profisc.actions'].getQrCode(account_move_id)
        # raise UserError(f"returned_json:{returned_json}")

    @api.model
    def getFiscPdf(self, account_move_id):
        self.env['profisc.actions'].getFiscPdf(account_move_id)
        # raise UserError(f"returned_json:{returned_json}")

    @api.model
    def getEinvoicePdf(self, account_move_id):
        self.env['profisc.actions'].getEinvoicePdf(account_move_id)
        # raise UserError(f"returned_json:{returned_json}")
