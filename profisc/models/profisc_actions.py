import json, logging, requests, textwrap
from odoo import api, models, _
from odoo.exceptions import UserError
from datetime import date, datetime

_logger = logging.getLogger(__name__)


class DateEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


class profisc_actions(models.Model):
    _name = 'profisc.actions'
    _description = "Profisc api caller model"

    @api.model
    def getTaxPayer(self, nuis):
        if self.env['other_functions'].nuis_regex_checker(nuis):
            company = self.env['profisc.auth'].get_current_company()
            auth_object = {
                "object": "GetTaxpayersRequest",
                "value": nuis,
                "username": self.env.user.name,
                "company": company.profisc_company_id
            }
            res = requests.post(f"{company.profisc_api_endpoint}{company.profisc_search_endpoint}",
                                data=json.dumps(auth_object),
                                headers=self.env['profisc.auth'].generateHeaders())

            if res.status_code == 200:
                return res.json()
            if res.status_code in (401, 403):
                self.env['profisc.auth'].profisc_login()
                return self.getTaxPayer(nuis)
            else:
                raise UserError(res.text)
        else:
            raise UserError("Invalid nuis")

    def updateRecord(self, record, res):
        record.write({
            'profisc_iic': res['iic'],
            'profisc_fic': res['fic'],
            'profisc_eic': res['eic'],
            'profisc_qr_code': res['qrUrl'],
            'profisc_status_control': '3',
            'profisc_fisc_status_sale': 'Y',
            'profisc_ubl_id': res['ublId']

        })
        self.env.cr.commit()

    @api.model
    def sendToProfisc(self, account_move_id):
        company = self.env['profisc.auth'].get_current_company()
        record = self.env['account.move'].browse(account_move_id)

        if record.profisc_cis_type == '0':
            self.error(record.id, "The invoice is in incorrect CIS Type")

        if record.state in 'posted':
            invoice_payload = self.createInvoicePayload(record)

            auth_object = {
                "object": invoice_payload,
                "invoiceId": record.name,
                "invoiceType": 'invoice' if record.move_type in ('out_invoice', 'out_refund') else 'credit',
                "isEinvoice": int(record.profisc_cis_type) == 1,  # = Fiscalization OR No Fiscalization
            }
            _logger.info('auth_object:: %s!' % auth_object)
            response = requests.post(f"{company.profisc_api_endpoint}{company.profisc_upload_invoice}",
                                     data=json.dumps(auth_object),
                                     headers=self.env['profisc.auth'].generateHeaders())
            res = response.json()
            self.handleResponse(record, res, response)

    def handleResponse(self, record, res, response):
        if response.status_code == 200:
            if res['status'] and res['errorCode'] is None:
                self.updateRecord(record, res)
                self.getQrCode(record.id)
                self.info(record.id, "Fiskalizim i suksesshem")

            elif res['errorCode'] == 'T991':
                record.write({
                    'profisc_status_control': '2',
                    'profisc_fisc_status_sale': 'E' + res['errorCode'],
                    'profisc_fic_error_code': res['errorCode'],
                    'profisc_eic_error_description': res['faultDescription']
                })
                self.env.cr.commit()
                self.getQrCode(record.id)
                self.warning(record.id, "Received error T991, the invoise set to retry status")

            elif res['errorCode'] == 'T010':
                self.updateRecord(record, res)
                self.getQrCode(record.id)
                self.warning(record.id, "Received error T010, the invoise set to success status")

            else:
                record.write({
                    'profisc_status_control': '0',
                    'profisc_fisc_status_sale': 'E' + res['errorCode'],
                    'profisc_fic_error_code': res['errorCode'],
                    'profisc_eic_error_description': res['faultDescription']
                })
                self.env.cr.commit()
                self.error(record.id, res['faultDescription'])

            # raise UserError("Error with code:"+res['errorCode']+", description:"+res['faultDescription'])
        elif response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            self.sendToProfisc(record.id)
        else:
            self.error(record.id, response.text)

    # def handeT991(self):

    def createInvoicePayload(self, record):
        current_time = datetime.now().strftime("%H:%M:%S")
        invoice_json = {
            "invoiceId": record.name,
            'tcr': record.profisc_tcr_code if record.profisc_tcr_code else record.company_id.default_tcr,
            'branch': record.profisc_bu_code if record.profisc_bu_code else None,
            'date': str(record.invoice_date.strftime("%d/%m/%Y ") + current_time),
            'dueDate': str(record.invoice_date_due.strftime("%d/%m/%Y ") + current_time),
            'invoiceCode': record.profisc_invoice_type,  # new optional value e fushes type?
            'invoiceType': 'invoice' if record.move_type in ('out_invoice', 'out_refund') else 'credit',
            'currency': record.currency_id.name,
            'exchangeRate': record.amount_total_signed / record.amount_total_in_currency_signed if record.currency_id != record.company_currency_id else 1.00,
            'sendEInv': int(record.profisc_cis_type) == 1,  # = Fiscalization OR No Fiscalization
            'taxScheme': "Normal",
            'paymentTerm': record.invoice_payment_term_id.profisc_payment_code,
            'bankorCash': record.invoice_payment_term_id.profisc_payment_code_description,
            'profileId': record.profisc_profile_id,
            'noteToCustomer': record.ref if record.ref else "",
            "customer": {
                "name": record.partner_id.name,
                "nipt": record.partner_id.vat,
                "address": record.partner_id.street if record.partner_id.street else "-",
                "cityName": record.partner_id.city if record.partner_id.city else "-",
                "countryCode": self.env['other_functions'].convert_country_code(record.partner_id.country_code)
            },
            "seller": {
                "name": record.company_id.display_name,
                "nipt": record.company_id.vat,
                "address": record.company_id.street if record.company_id.street else "-",
                "cityName": record.company_id.city if record.company_id.city else "-",
                "countryCode": self.env['other_functions'].convert_country_code(record.company_id.country_code),
                # record.company_id.country_code
            },
            'items': [],
            'totalNeto': record.amount_untaxed,
            'totalVat': record.amount_total - record.amount_untaxed,
            'total': record.amount_total,
            'bankAccounts': []
        }

        if(record.partner_bank_id):
            bank_json = {
                'iban': record.partner_bank_id.acc_number,
                'bankName': record.partner_bank_id.bank_id.name,
                'swift': record.partner_bank_id.bank_id.bic
            }
            invoice_json['bankAccounts'].append(bank_json)

        if record.profisc_profile_id == "P12":
            invoice_json['customer'], invoice_json['seller'] = invoice_json['seller'], invoice_json['customer']
            invoice_json['selfinvoiceType'] = record.profisc_self_invoice_type
            invoice_json['isReverseCharge'] = record.profisc_reverse_charge
        elif record.profisc_profile_id in ["P2", "P10"]:
            if record.profisc_start_date:
                invoice_json['startDate'] = str(record.profisc_start_date.strftime("%d/%m/%Y ") + current_time)
            if record.profisc_end_date:
                invoice_json['endDate'] = str(record.profisc_end_date.strftime("%d/%m/%Y ") + current_time)

        if record.partner_id.profisc_customer_vat_type:
            invoice_json['customer']['idType'] = record.partner_id.profisc_customer_vat_type
        else:
            invoice_json['customer']['idType'] = "9923"

        if record.profisc_subseq:
            invoice_json['subseq'] = record.profisc_subseq

        if record.profisc_reference_invoice_iic:
            invoice_json['refIic'] = str(record.profisc_reference_invoice_iic)  # new corrective

        if record.profisc_reference_invoice_date:
            invoice_json['refIssueDate'] = str(record.profisc_reference_invoice_date.strftime("%Y-%m-%d"))

        if self.env.user.profisc_operator_code:
            invoice_json['operatorCode'] = self.env.user.profisc_operator_code

        for line in record.invoice_line_ids:
            tax = line.tax_ids
            price_include = tax.price_include

            item_price = line.price_unit
            total_line_neto = line.price_subtotal

            if price_include:
                item_price = line.price_unit / (1 + tax.amount / 100)

            total_line_vat = total_line_neto * (1 + tax.amount / 100) - total_line_neto  # formula e pare

            coef = 1
            if record.profisc_profile_id == "P10":
                coef = -1

            invoice_line = {
                'name': textwrap.shorten(line.name, width=50, placeholder="..."),
                "unit": line.product_uom_id.profisc_uom_val.code if line.product_uom_id.profisc_uom_val else line.product_uom_id.name,
                'quantity': coef * line.quantity,
                'price': item_price,
                "discount":  item_price * line.quantity * (line.discount / 100.0) * coef,
                "vat": tax.amount,
                "vatScheme": tax.description,
                "totalLineNeto": coef * total_line_neto,
                "totalLineVat": coef * total_line_vat
            }
            if tax.profisc_tax_exempt_reason:
                invoice_line['exemptReasonCode'] = tax.profisc_tax_exempt_reason
                invoice_line['exemptReasonName'] = tax.profisc_tax_exempt_reason

            invoice_json['items'].append(invoice_line)
        return invoice_json

    def getQrCode(self, account_move_id):
        record = self.env['account.move'].browse(account_move_id)
        if record.profisc_qr_code is None:
            return False
        if record.profisc_qr_code_check:
            return False

        encoded = self.env['other_functions'].createQrCode(record.profisc_qr_code)

        record.write({"profisc_qr_code_check": encoded})
        self.env.cr.commit()
        self.add_attachment(record, "qr_code", encoded)

    def getFiscPdf(self, account_move_id):

        record = self.env['account.move'].browse(account_move_id)
        company = self.env['profisc.auth'].get_current_company()
        detected_error = False
        message = ""

        if not record.profisc_fic:
            detected_error = True
            message = "For getting the Fiscalization invoice PDF, FIC parameter needs to be valid!"
        if record.profisc_fisc_downloaded:
            detected_error = True
            message = "Fiscalization PDF is already downloaded!"

        if detected_error:
            self.error(record.id, message)
            raise UserError(message)

        payload = {
            "object": "GetFiscPDF",
            "params": json.dumps({"iic": record.profisc_iic}),
            "username": self.env.user.name,
            "company": company.profisc_company_id
        }
        # raise UserError(f"payload::{payload}")
        return self.getFile(record, payload, "fisc_invoice_pdf")

    def getEinvoicePdf(self, account_move_id):
        company = self.env['profisc.auth'].get_current_company()
        record = self.env['account.move'].browse(account_move_id)
        detected_error = False
        message = ""
        if not record.profisc_eic:
            detected_error = True
            message = "For getting the Electronic invoice PDF, EIC parameter needs to be valid!"

        if record.profisc_einvoice_downloaded:
            detected_error = True
            message = "Electronic PDF is already downloaded!"

        if detected_error:
            self.error(record.id, message)

        payload = {
            "object": "GetEinvoicesRequest",
            "params": json.dumps({"dataFrom":"CIS", "eic": record.profisc_eic}),
            "username": self.env.user.name,
            "company": company.profisc_company_id
        }
        self.getFile(record, payload, "e_invoice_pdf")
        # raise UserError(json.dumps(payload))

    def getFile(self, record, payload, invoice_type):
        company = self.env['profisc.auth'].get_current_company()
        response = requests.post(f"{company.profisc_api_endpoint}{company.profisc_search_endpoint}",
                                 data=json.dumps(payload),
                                 headers=self.env['profisc.auth'].generateHeaders())
        res = response.json()
        if response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            if invoice_type == 'e_invoice_pdf':
                self.getEinvoicePdf()
            else:
                self.getFiscPdf()
        elif response.status_code == 200:
            if res['status'] and res['error'] is None and len(res['content']) > 0:
                content = res['content'][0]
                if invoice_type == 'e_invoice_pdf':
                    base64_pdf = content['pdf']
                else:
                    base64_pdf = content

                self.add_attachment(record, invoice_type, base64_pdf)
                return None
            else:
                self.error(record.id, "Requested file not found.")

        return {'success': True, "status_code": response.status_code, "message": "Veprim i suksesshem"}

    def add_attachment(self, record, attachment_name, attachment_data, model='account.move'):

        # _logger.info('attachment_data:: %s!'  %(attachment_data))
        attachment_data_bytes = attachment_data.encode('utf8').decode('ascii')
        attachment_vals = {
            'name': f"{attachment_name}",
            'datas': attachment_data_bytes,
            'res_model': model,
            'res_id': record.id,
        }
        attachment = self.env['ir.attachment'].create(attachment_vals)
        # Associate attachment with move
        if attachment_name == "e_invoice_pdf":
            record.write({'attachment_ids': [(4, attachment.id)], "profisc_einvoice_downloaded": True})
        elif attachment_name == "fisc_invoice_pdf":
            record.write({'attachment_ids': [(4, attachment.id)], "profisc_fisc_downloaded": True})
        else:
            record.write({'attachment_ids': [(4, attachment.id)]})
        self.env.cr.commit()
        return None

    def error(self, move_id, message):
        self.writeActivity(move_id, message, "Error")
        raise UserError(message)

    def warning(self, move_id, message):
        self.writeActivity(move_id, message, "Kujdes")

    def info(self, move_id, message):
        self.writeActivity(move_id, message, "Info")

    def writeActivity(self, move_id, message, log_type):
        self.env['mail.message'].create({
            'model': 'account.move',
            'res_id': move_id,
            'message_type': 'comment',
            'body': f"{log_type} action in fiscalization:<br/> {message}",
        })
        self.env.cr.commit()

    def add_attachments_vendorBill(self, eic, old_obj):

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

            self.env['profisc.actions'].add_attachment(old_obj, 'purchase_pdf', item['pdf'])

            old_obj.profisc_einvoice_downloaded = True
            old_obj.extract_state = 'done'

            old_obj_purchase = self.env['profisc.purchase_book'].search([('id', '=', old_obj.profisc_purchaseBill_id)])

            old_obj_purchase.write({'attachment_ids': [(4, old_obj.attachment_ids.id)], 'purch_is_AttachmentExtracted': True})

            print(old_obj.attachment_ids.ids)

            old_obj_purchase.message_post(body="U shtua nje attachment e-invoice", attachment_ids=old_obj.attachment_ids.ids)

            self.env.cr.commit()

        elif response.status_code in (401, 403):
            self.env['profisc.auth'].profisc_login()
            return self.add_attachments_vendorBill(eic, old_obj)
        else:
            raise UserError(_("PDF nuk ekziston"))
