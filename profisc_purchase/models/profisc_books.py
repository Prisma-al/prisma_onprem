import json
import logging
import re
import calendar
from functools import reduce

import requests
import textwrap
import base64

from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import date, datetime

_logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


class profisc_book_actions(models.Model):
    _name = 'profisc.book_actions'
    _description = "Profisc purchase actions model"

    @api.model
    def get_all_purchase_books(self, from_date):

            count = 0

            # request_manager = self.env['request.manager']

            company = self.env['profisc.auth'].get_current_company()
            endpoint = f"{company.profisc_api_endpoint}{company.profisc_search_endpoint}"

            payload = {
                "object": "GetPurchaseFull",
                "value": "",
                "params": json.dumps(
                    {"purchaseInvoiceExtracted.period": from_date}),
                "username": company.profisc_username,
                "company": company.profisc_company_id,
            }

            _logger.info('get_all_purchase_books>payload> %s' % payload)

            response = requests.post(f"{endpoint}",
                                     data=json.dumps(payload, cls=DateEncoder),
                                     headers=self.env['profisc.auth'].generateHeaders())

            if response.status_code == 200:
                res = response.json()
                if res['status'] is True and len(res['content']) > 0:

                    for item in res['content'][0]:

                        if item:

                            json_string = json.dumps(item, cls=DateEncoder)
                            # First, encode the item as UTF-8
                            utf8_encoded_item = json_string.encode('utf-8')
                            # Then, encode the UTF-8 encoded bytes to base64
                            base64_encoded_item = base64.b64encode(utf8_encoded_item).decode('utf-8')

                            values = {

                                'name': item['ublId'] + "_json.txt",

                                'res_model': 'ir.ui.view',

                                'res_id': False,

                                'type': 'binary',

                                'public': True,

                                'datas': base64_encoded_item,

                            }

                            attachment_id = self.env['ir.attachment'].sudo().create(values)

                            old_obj = self.env['profisc.purchase_book'].search([('purch_fic', '=', item['fic']), ('company_id', '=', company.id)],limit=1)

                            if not old_obj:

                                if item['invoiceDate'] != None:
                                    issue_date = datetime.fromtimestamp(item['invoiceDate'] / 1000.0)
                                else:
                                    issue_date = None

                                if item['startDate'] != None:
                                    startDate = datetime.fromtimestamp(item['startDate'] / 1000.0)
                                else:
                                    startDate = None

                                if item['dueDate'] != None:
                                    dueDate = datetime.fromtimestamp(item['dueDate'] / 1000.0)
                                else:
                                    dueDate = None

                                if item['endDate'] != None:
                                    endDate = datetime.fromtimestamp(item['endDate'] / 1000.0)
                                else:
                                    endDate = None

                                if item['eic'] != None:
                                    eic = item['eic']
                                else:
                                    eic = None

                                currency = self.env['res.currency'].search([('name', '=', 'ALL')], limit=1)

                                if item['supplier']:
                                    purch_sellerName = item['supplier']['name']
                                    purch_sellerNuis = item['supplier']['nipt']
                                    purch_seller_address = item['supplier']['address']
                                    purch_seller_town = item['supplier']['town']
                                    purch_seller_country = item['supplier']['country']

                                if company.prof_pu_param4:
                                    partner = self.env['res.partner'].search([('vat', '=', purch_sellerNuis)],limit=1)
                                    if not partner:
                                        partner = self.create_supplier(purch_sellerName, purch_sellerNuis, purch_seller_address, purch_seller_town)
                                    partner_id = partner.id
                                else:
                                    partner_id = None

                                count += 1

                                print(currency.name)

                                obj = {
                                    "company_id": company.id,
                                    "purch_ublId": item['ublId'],
                                    "purch_currency_id": currency.id,
                                    "purch_imported_date": date.today(),
                                    "purch_fic": item['fic'],
                                    "purch_eic": eic,
                                    "purch_cis_status": item['cisStatus'],
                                    "purch_issue_date": issue_date,
                                    "purch_start_date": startDate,
                                    "purch_end_date": endDate,
                                    "purch_due_date": dueDate,
                                    "purch_iic": item['iic'],
                                    "purch_fiscInvoiceNumber": item['fiscInvoiceNumber'],
                                    "purch_invoiceType": item['invoiceType'],
                                    "purch_paymentType": item['paymentType'],
                                    "purch_qr_url": item['qrUrl'],
                                    "purch_amount": item['totalWVat'],
                                    "purch_tax_excluded": item['totalWoVat'],
                                    "purch_tax_value": item['totalVat'],
                                    "purch_period": item['period'],
                                    "partner_id": partner_id,
                                    "purch_is_einvoice": item['einvoice'],
                                    "purch_is_custom": item['custom'],
                                    "purch_is_onlyFisc": item['onlyFisc'],
                                    "purch_sellerName": purch_sellerName,
                                    "purch_sellerNuis": purch_sellerNuis,
                                    "purch_seller_address": purch_seller_address,
                                    "purch_seller_town": purch_seller_town,
                                    "purch_seller_country": purch_seller_country,
                                    "purch_exRate": item['exRate'],
                                    "purch_base_currency": item['currency'],
                                    "purch_total_in_currency": item['totalWVat'] / item['exRate'],
                                }

                                book = self.env['profisc.purchase_book'].create(obj)

                                book.message_post(body="U shtua nje attachment json.txt", attachment_ids=attachment_id.ids)

                                if company.prof_pu_param4:
                                    book.write({'purch_isSupplierCreated': True})

                                for item_line in item['items']:

                                    if item_line['vatRate'] == 20:

                                        template = self.env['account.tax'].search(
                                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 20),
                                             ('active', '=', 'True')], limit=1)

                                    elif item_line['vatRate'] == 10:

                                        template = self.env['account.tax'].search(
                                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 10),
                                             ('active', '=', 'True')], limit=1)

                                    elif item_line['vatRate'] == 6:

                                        template = self.env['account.tax'].search(
                                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 6),
                                             ('active', '=', 'True')], limit=1)

                                    elif item_line['vatRate'] == 0:

                                        template = self.env['account.tax'].search(
                                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 0),
                                             ('active', '=', 'True'),
                                             ('profisc_tax_exempt_reason', '=', item_line['vatExemptionReason'])],
                                            limit=1)
                                    else:
                                        template = False

                                    if item_line:

                                        print(item_line['vatAmount'])

                                        obj_item = {
                                            "book_id": book.id,
                                            "itemName": item_line['name'],
                                            "itemDescription": item_line['description'],
                                            "itemCode": item_line['code'],
                                            "unitOfMeasure": item_line['uom'],
                                            "itemQuantity": item_line['quantity'],
                                            "total": abs(item_line['lineExtAmount']),
                                            "unitPrice": abs(item_line['priceAmount']),
                                            "vatRate": item_line['vatRate'],
                                            "vatAmount": abs(item_line['vatAmount']),
                                            "tax_ids": template.id if template else False,
                                        }

                                        self.env['profisc.purchase_book.lines'].create(obj_item)

                    self.env.cr.commit()
                return count
            elif response.status_code in (401, 403):
                self.env['profisc.auth'].profisc_login()
                return self.get_all_purchase_books(from_date)
            else:
                raise UserError(response.text)

    @api.model
    def import_bills(self, active_invoices):

        print(active_invoices)
        journal = self.env['account.journal'].search([('type', '=', 'purchase')],  limit=1)
        company = self.env['profisc.auth'].get_current_company()
        print(journal.id)

        errors = []

        for bill in active_invoices:

            if bill.purch_is_imported == "imported":
                errors.append(bill.purch_fic)
                print("TEST")
            else:

                twentypercent_totsum = 0
                tenpercent_totsum = 0
                sixpercent_totsum = 0
                zeropercent_totsum = 0
                notax_totsum = 0

                currency = self.env['res.currency'].search([('name', '=', bill.purch_base_currency)], limit=1)

                bill_obj = {
                    "company_id": bill.company_id.id,
                    "move_type": "in_invoice",
                    "partner_id": bill.partner_id.id,
                    "journal_id": journal.id,
                    "currency_id": currency.id,
                    "profisc_fic": bill.purch_fic,
                    "profisc_iic": bill.purch_iic,
                    "profisc_eic": bill.purch_eic,
                    "invoice_date_due": bill.purch_due_date,
                    "date": bill.purch_issue_date,
                    "invoice_date": bill.purch_issue_date,
                    "profisc_purchaseBill_id": bill.id,
                    "profisc_fisc_status_sale": "Y",
                    "profisc_fisc_status": bill.purch_cis_status,
                    "profisc_isEinvoice": bill.purch_is_einvoice,
                    "profisc_isFiscalized": True,
                    "profisc_ubl_id": bill.purch_ublId,
                    "profisc_currency_rate": str(bill.purch_exRate),
                }

                vendorBill = self.env['account.move'].create(bill_obj)

                bill.purch_VendorBill_id = vendorBill.id

                print(bill.id)
                if company.prof_pu_param3:

                    for lines in bill.book_lines_ids:

                        if lines.vatRate == 20:

                            twentypercent_totsum += lines.unitPrice * lines.itemQuantity

                        elif lines.vatRate == 10:

                            tenpercent_totsum += lines.unitPrice * lines.itemQuantity

                        elif lines.vatRate == 6:

                            sixpercent_totsum += lines.unitPrice * lines.itemQuantity

                        elif lines.vatRate == 0:

                            zeropercent_totsum += lines.unitPrice * lines.itemQuantity

                        else:

                            notax_totsum += lines.unitPrice * lines.itemQuantity

                    if twentypercent_totsum != 0:

                        template = self.env['account.tax'].search(
                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 20), ('active', '=', 'True'),
                            ('purch_allow_product_mapping', '=', 'True')], limit=1)

                        print(template.name)

                        bill_obj = {
                            "move_id": vendorBill.id,
                            "product_id": template.purch_product_id.id,
                            "price_unit": twentypercent_totsum,
                        }

                        self.env['account.move.line'].create(bill_obj)

                    if tenpercent_totsum != 0:

                        template = self.env['account.tax'].search(
                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 10), ('active', '=', 'True'),
                            ('purch_allow_product_mapping', '=', 'True')], limit=1)

                        bill_obj = {
                            "move_id": vendorBill.id,
                            "product_id": template.purch_product_id.id,
                            "price_unit": tenpercent_totsum,
                        }

                        self.env['account.move.line'].create(bill_obj)


                    if sixpercent_totsum != 0:

                        template = self.env['account.tax'].search(
                        [('type_tax_use', '=', 'purchase'), ('amount', '=', 6), ('active', '=', 'True'),
                        ('purch_allow_product_mapping', '=', 'True')], limit=1)

                        bill_obj = {
                            "move_id": vendorBill.id,
                            "product_id": template.purch_product_id.id,
                            "price_unit": sixpercent_totsum,
                            }

                        self.env['account.move.line'].create(bill_obj)

                    if zeropercent_totsum != 0:

                        template = self.env['account.tax'].search(
                            [('type_tax_use', '=', 'purchase'), ('amount', '=', 0), ('active', '=', 'True'),
                             ('profisc_tax_exempt_reason', '=', lines.tax_ids.profisc_tax_exempt_reason),
                             ('purch_allow_product_mapping', '=', 'True')], limit=1)

                        if template.purch_allow_product_mapping:

                            bill_obj = {
                               "move_id": vendorBill.id,
                                "product_id": template.purch_product_id.id,
                                "price_unit": zeropercent_totsum,
                                }

                            self.env['account.move.line'].create(bill_obj)

                else:

                    for lines in bill.book_lines_ids:

                        if company.prof_pu_param2:
                            unit = self.env['profisc.uoms'].search([('code', '=', 'XCP')], limit=1)
                        else:
                            unit = self.env['profisc.uoms'].search([('code', '=', lines.unitOfMeasure)], limit=1)
                            if unit == False:
                                obj = {
                                    "name": lines.unitOfMeasure,
                                    "code": lines.unitOfMeasure,
                                    "is_active": True
                                }
                                unit = self.env['profisc.uoms'].create(obj)

                        if lines.vatRate == 20:

                            template = self.env['account.tax'].search(
                                [('type_tax_use', '=', 'purchase'), ('amount', '=', 20), ('active', '=', 'True')], limit=1)

                            print(template.name)

                            bill_obj = {
                                "move_id": vendorBill.id,
                                "product_id": None,
                                "price_unit": lines.unitPrice,
                                "quantity": lines.itemQuantity,
                                "tax_ids": template,
                                "name": lines.itemName,
                                "profisc_uom": unit.id,
                            }

                            self.env['account.move.line'].create(bill_obj)

                        elif lines.vatRate == 10:

                            template = self.env['account.tax'].search(
                                [('type_tax_use', '=', 'purchase'), ('amount', '=', 10), ('active', '=', 'True')], limit=1)

                            bill_obj = {
                                "move_id": vendorBill.id,
                                "product_id": None,
                                "price_unit": lines.unitPrice,
                                "quantity": lines.itemQuantity,
                                "tax_ids": template,
                                "name": lines.itemName,
                                "profisc_uom": unit.id,
                            }
                            self.env['account.move.line'].create(bill_obj)

                        elif lines.vatRate == 6:

                            template = self.env['account.tax'].search(
                                [('type_tax_use', '=', 'purchase'), ('amount', '=', 6), ('active', '=', 'True')], limit=1)

                            bill_obj = {
                                "move_id": vendorBill.id,
                                "product_id": None,
                                "price_unit": lines.unitPrice,
                                "quantity": lines.itemQuantity,
                                "tax_ids": template,
                                "name": lines.itemName,
                                "profisc_uom": unit.id,
                            }

                            self.env['account.move.line'].create(bill_obj)

                        elif lines.vatRate == 0:

                            template = self.env['account.tax'].search(
                                [('type_tax_use', '=', 'purchase'), ('amount', '=', 0), ('active', '=', 'True'),
                                 ('profisc_tax_exempt_reason', '=', lines.tax_ids.profisc_tax_exempt_reason)], limit=1)

                            bill_obj = {
                                "move_id": vendorBill.id,
                                "product_id": None,
                                "price_unit": lines.unitPrice,
                                "quantity": lines.itemQuantity,
                                "tax_ids": template,
                                "name": lines.itemName,
                                "profisc_uom": unit.id,
                            }

                            self.env['account.move.line'].create(bill_obj)

            bill.purch_is_imported = "imported"
            self.env.cr.commit()

        return errors

    @api.model
    def accept_bills(self, eics, status):

        errors = []

        for eic in eics:

            eic_string = ''
            bill = self.env['profisc.purchase_book'].search([('purch_eic', '=', eic)], limit=1)

            print(bill.purch_sellerName)

            if bill.purch_cis_status != 'DELIVERED':
                errors.append(bill.purch_fic)
                print("Error")
                continue

            eic_string += eic
            print((eic_string))

            company = self.env['profisc.auth'].get_current_company()
            endpoint = f"{company.profisc_api_endpoint}{company.profisc_invoiceStatus}"

            payload = {
                "params": json.dumps({"dataFrom": "CIS"}),
                "value": eic_string,
                "status": status,
                "nuis": company.vat,
                "username": "",
                "company": company.profisc_company_id
            }

            response = requests.post(f"{endpoint}",
                                     data=json.dumps(payload, cls=DateEncoder),
                                     headers=self.env['profisc.auth'].generateHeaders())

            if response.status_code == 200:
                res = response.json()
                print(res)
                if res['status']:
                    bill.write({'purch_cis_status': status})
                    print(bill.purch_cis_status)
                    if bill.purch_VendorBill_id:
                        vbill = self.env['account.move'].search([('id', '=', bill.purch_VendorBill_id)])
                        vbill.profisc_fisc_status = status
            elif response.status_code in (401, 403):
                self.env['profisc.auth'].profisc_login()
                return self.accept_bills(eics, status)
        self.env.cr.commit()
        return errors

    @api.model
    def create_supplier(self, name, nuis, address, town):

        partner = {
            "name": name,
            "vat": nuis,
            "street": address,
            "city": town,

        }

        created_partner = self.env['res.partner'].create(partner)

        return created_partner

    def add_attachments_CisPurchase(self, eic, old_obj):

        company = self.env['profisc.auth'].get_current_company()
        endpoint = f"{company.profisc_api_endpoint}/endpoint/v2/apiExtractPurchaseInvoice"

        payload = {
                "params": json.dumps({"eic": eic}),
                "nuis": company.vat,
                "username": ""
        }

        response = requests.post(f"{endpoint}",
                                 data=json.dumps(payload, cls=DateEncoder),
                                 headers=self.env['profisc.auth'].generateHeaders())

        if response.status_code == 200:
            res = response.json()

            print(res)

            item = res['content'][0]

            print(item['pdf'])

            self.env['profisc.actions'].add_attachment(old_obj, 'purchase_pdf', item['pdf'], 'profisc.purchase_book')

            old_obj.purch_is_AttachmentExtracted = True

            old_obj.message_post(body="U shtua nje attachment e-invoice", attachment_ids=old_obj.attachment_ids.ids)

            if old_obj.purch_is_imported == "imported":

                print(old_obj.purch_is_imported)

                bill = self.env['account.move'].search([('id', '=', old_obj.purch_VendorBill_id)])

                bill.write({'attachment_ids': [(4, old_obj.attachment_ids.id)], 'profisc_einvoice_downloaded': True, 'extract_state': 'done'})

                print(bill.attachment_ids.ids)

                bill.message_post(body="U shtua nje attachment e-invoice", attachment_ids=old_obj.attachment_ids.ids)

                self.env.cr.commit()

        elif response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            return self.add_attachments_CisPurchase(eic, old_obj)
        else:
            raise UserError(_("PDF nuk ekziston"))

    @api.model
    def checkSingleInvoiceStatus(self, object):

            company = self.env['profisc.auth'].get_current_company()
            endpoint = f"{company.profisc_api_endpoint}{company.profisc_checkStatus}"

            payload = {
                "object": "GetEinvoicesRequestV4",
                "params": json.dumps({"eic": object.purch_eic}),
                "value": None,
                "company": company.profisc_company_id
            }

            response = requests.post(f"{endpoint}",
                                    data=json.dumps(payload, cls=DateEncoder),
                                    headers=self.env['profisc.auth'].generateHeaders())

            if response.status_code == 200:
                res = response.json()
                print(res)
                if res['status']:
                    content = res['content'][0]
                    print(content)
                    if content['status'] != object.purch_cis_status:
                        object.purch_cis_status = content['status']
                        object.post_message("Statusi i fatures eshte ndryshuar ne " + content['status'])
                        if object.is_imported:
                            bill = object.env['account.move'].search([('id', '=', object.purch_VendorBill_id)])
                            bill.profisc_fisc_status = content['status']
                            bill.post_message("Statusi i fatures eshte ndryshuar ne " + content['status'])
            elif response.status_code in (401, 403):
                self.env['profisc.auth'].profisc_login()
                return self.checkSingleInvoiceStatus()
            else:
                raise UserError(response.text)

    @api.model
    def chechStatusPeriod(self, month, year):

        count = 0

        from_date = datetime(int(year), int(month), 1)

        res = reduce(lambda x, y: y[1], [calendar.monthrange(from_date.year, from_date.month)], None)

        to_date = datetime(int(year), int(month), res)

        cis_from_date = from_date.strftime("%Y-%m-%d") + "T00:00:00.000Z"
        cis_to_date = to_date.strftime("%Y-%m-%d") + "T00:00:00.000Z"

        company = self.env['profisc.auth'].get_current_company()
        endpoint = f"{company.profisc_api_endpoint}{company.profisc_checkStatus}"

        payload = {
                "object": "GetEinvoicesRequestV4",
                "value": None,
                "params": json.dumps({"dataFrom":"CIS","partyType":"BUYER"}),
                "fromDate": cis_from_date,
                "toDate": cis_to_date,
                "username": "",
                "company": company.profisc_company_id
        }


        response = requests.post(f"{endpoint}",
                                 data=json.dumps(payload, cls=DateEncoder),
                                 headers=self.env['profisc.auth'].generateHeaders())

        if response.status_code == 200:
            res = response.json()
            print(res)
            if res['status']:
                content = res['content']

                for item in content:
                    print(item)
                    old_obj = (self.env['profisc.purchase_book'].search([('purch_eic', '=', item['eic'])], limit=1))
                    if old_obj:
                        if old_obj.purch_cis_status != item['status']:
                            count += 1
                            old_obj.write({'purch_cis_status': item['status']})
                            if old_obj.purch_is_imported:
                                bill = self.env['account.move'].search([('id', '=', old_obj.purch_VendorBill_id)])
                                bill.profisc_fisc_status = item['status']

        return count

    @api.model
    def deleteInvoices(self, array):
        for item in array:
            if item:
                old_obj_lines = self.env['profisc.purchase_book.lines'].search([('book_id', '=', item.id)])
                for line in old_obj_lines:
                    line.unlink()
                item.unlink()