from odoo import models, fields, api


class ProfiscImportWizard(models.TransientModel):
    _name = 'profisc.import_wizard'
    _description = 'Profisc purchase import bill wizard'

    def import_bills(self):
        a = 0



