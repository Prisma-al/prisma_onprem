from odoo import api, fields, models
import requests

class RestApiHelper(models.Model):
    _name = 'rest.api.helper'
    _description = 'REST API Helper'

    name = fields.Char(string='Name', required=True, default='REST API Helper')

    @api.model
    def make_request(self, url, method='GET', headers=None, data=None, json=None):
        if method == 'GET':
            response = requests.get(url, headers=headers, data=data)
        elif method == 'POST':
            response = requests.post(url, headers=headers, data=data, json=json)
        # Add other methods if needed
        return response
