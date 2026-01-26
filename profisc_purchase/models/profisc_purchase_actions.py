import json
import logging
import re
import requests
import textwrap

from odoo import api, models
from odoo.exceptions import UserError
from datetime import date, datetime

_logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


def add_extracted_info(eic, item):
    if item['purchaseInvoiceExtracted']:
        inv_ext = item['purchaseInvoiceExtracted']
        obj = {
            "purch_currency": inv_ext['currency'],
            "purch_currency_ex_rate": inv_ext['exRate'],
            "purch_iic": inv_ext['iic'],
            "purch_fic": inv_ext['fic'],
            "purch_cis_status": item['myPurchaseStatus']['name'],
            "purch_profile_id": inv_ext['profileId'],
            "purch_qr_url": inv_ext['qrUrl'],
            "purch_tax_value": inv_ext['vatValue'],
            "purch_tax_inc_value": inv_ext['valueWVat'],
            "purch_tax_excluded": inv_ext['valueWoVat'],
        }

        if inv_ext['startDate']:
            obj["purch_start_date"] = datetime.fromtimestamp(inv_ext['startDate'] / 1000)

        if inv_ext['endDate']:
            obj["purch_end_date"] = datetime.fromtimestamp(inv_ext['endDate'] / 1000)

    else:
        raise UserError(f"Invoice with eic:{eic} is not extracted in Profisc")
    return obj


class profisc_purchase_actions(models.Model):
    _name = 'profisc.purchase_actions'
    _description = "Profisc purchase actions model"

    @api.model
    def get_all_invoices(self, from_date, to_date, invoice_type):

        # request_manager = self.env['request.manager']

        company = self.env['profisc.auth'].get_current_company()
        endpoint = f"{company.profisc_api_endpoint}{company.profisc_search_endpoint}"

        payload = {
            "object": "GetEinvoicesRequestV4",
            "value": "",
            "params": json.dumps({"dataFrom": "CIS", "partyType": invoice_type}),
            "fromDate": from_date,
            "toDate": to_date,
            "username": "bsholla",
            "company": "159"
        }
        _logger.info('get_all_invoices>payload> %s' % payload)

        response = requests.post(f"{endpoint}",
                                 data=json.dumps(payload, cls=DateEncoder),
                                 headers=self.env['profisc.auth'].generateHeaders())


        if response.status_code == 200:
            res = response.json()
            if res['status'] is True and len(res['content']) > 0:
                for item in res['content']:
                    old_obj = self.env['profisc.purchase_invoices'].search([('purch_eic', '=', item['eic'])], limit=1)
                    partner = self.env['res.partner'].search([('vat', '=', item['sellerTin'])], limit=1)
                    if not old_obj:
                        obj = {
                            "purch_eic": item['eic'],
                            "purch_doc_number": item['docNumber'],
                            "purch_issue_date": datetime.fromtimestamp(item['recDateTime'] / 1000),
                            "purch_due_date": datetime.fromtimestamp(item['dueDateTime'] / 1000),
                            "purch_cis_status": item['status'],
                            "purch_amount": item['amount'],
                            "purch_nuis": item['sellerTin'],
                            "purch_party_type": item['partyType']
                        }
                        if partner:
                            obj["purch_supplier_odoo"] = partner.name
                            obj["partner_id"] = partner.id

                        self.env['profisc.purchase_invoices'].create(obj)
                    else:
                        upd_obj = {
                            'purch_cis_status': item['status']
                        }
                        if partner:
                            upd_obj["purch_supplier_odoo"] = partner.name
                            upd_obj["partner_id"] = partner.id

                        old_obj.write(upd_obj)

                    self.env.cr.commit()

            return json.dumps(res, cls=DateEncoder)
        elif response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            return self.get_all_invoices(from_date, to_date, invoice_type)
        else:
            raise UserError(response.text)

    @api.model
    def extract_purchase_invoice_by_id(self, purchase_id):
        record = self.env['profisc.purchase_invoices'].browse(purchase_id)
        if not record.purch_is_extracted:
            return self.extract_purchase_invoice(record.purch_eic)
        return None

    @api.model
    def extract_purchase_invoice(self, eic):
        company = self.env['profisc.auth'].get_current_company()
        payload = {
            "params": json.dumps({"eic": eic}),
            "username": self.env.user.name,
            "company": company.profisc_company_id,
            "nuis": company.vat
        }

        response = requests.post(f"{company.profisc_api_endpoint}/endpoint/v2/apiExtractPurchaseInvoiceAndGetXmlBase64",
                                 data=json.dumps(payload, cls=DateEncoder),
                                 headers=self.env['profisc.auth'].generateHeaders())

        if response.status_code == 200:
            res = response.json()
            if res['status'] is True and len(res['content']) > 0:
                for item in res['content']:
                    old_obj = self.env['profisc.purchase_invoices'].search([('purch_eic', '=', item['eic'])], limit=1)
                    partner = self.env['res.partner'].search([('vat', '=', item['sellerTin'])], limit=1)
                    # _logger.info('item:: %s!' % json.dumps({'item': item}))
                    if old_obj:
                        obj = add_extracted_info(eic, item)
                        if partner:
                            obj["purch_supplier_odoo"] = partner.name
                            obj["partner_id"] = partner.id

                        self.add_attachments(item, old_obj)
                        self.add_invoice_lines(item, old_obj)

                        obj["purch_is_extracted"] = True
                        old_obj.write(obj)
                    else:
                        raise UserError(f"Invoice with eic:{eic} was not found")

                    self.env.cr.commit()
            return json.dumps(res, cls=DateEncoder)
        elif response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            return self.extract_purchase_invoice(eic)
        else:
            raise UserError(response.text)

    def add_attachments(self, item, old_obj):
        if item['pdf']:
            self.env['profisc.actions'].add_attachment(old_obj, 'purchase_pdf', item['pdf'],
                                                       'profisc.purchase_invoices')
        if item['extractXml']:
            self.env['profisc.actions'].add_attachment(old_obj, 'purchase_xml', item['extractXml'],
                                                       'profisc.purchase_invoices')

    def add_invoice_lines(self, item, old_obj):
        if item['purchaseItems'] and len(item['purchaseItems']) > 0:
            purchase_items = item['purchaseItems']
            for pi in purchase_items:
                inv_line = {
                    "itemName": pi['itemName'],
                    "itemCode": pi['itemCode'],
                    "itemDesc": pi['itemDesc'],
                    "priceAmount": pi['priceAmount'],
                    "lineExtAmount": pi['lineExtAmount'],
                    "vatRate": pi['vatRate'],
                    "vatCategory": pi['vatCategory'],
                    "vatExemptinReason": pi['vatExemptinReason'],
                    "allowance": pi['allowance'],
                    "allowanceCharge": pi['allowanceCharge'],
                    "quantity": pi['quantity'],
                    "unitOfMeasurement": pi['unitOfMeasurement'],
                    'invoice_id': old_obj.id
                }
                self.env['profisc.purchase_invoice.lines'].create(inv_line)

    @api.model
    def import_invoice_to_vendor(self):
        data = {
            'name': '20_pc',
            'type': 'product',
            'list_price': 100,
            'standard_price': 0,
        }
        invoice = self.env['profisc.product.wizard'].create_product(data)
        _logger.info(f"Created invoice with id:{invoice}")
