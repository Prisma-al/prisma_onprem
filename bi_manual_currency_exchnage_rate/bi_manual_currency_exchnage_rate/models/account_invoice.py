# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.

from functools import lru_cache
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from contextlib import contextmanager
from odoo.tools import float_is_zero, float_round, float_compare, OrderedSet,float_repr
from collections import defaultdict


class InheritProductProduct(models.Model):
    _inherit = 'product.product'
    
    def _prepare_out_svl_vals(self, quantity, company):
        """Prepare the values for a stock valuation layer created by a delivery.

        :param quantity: the quantity to value, expressed in `self.uom_id`
        :return: values to use in a call to create
        :rtype: dict
        """
        self.ensure_one()
        find_active = self._context.get('active_id')
        find_sale_order = self.env['sale.order'].browse(find_active)
       
        if find_sale_order:
            if find_sale_order.sale_manual_currency_rate_active:
                manual_currency_rate = self.standard_price
            else:
                manual_currency_rate = self.standard_price
        else:
            manual_currency_rate = self.standard_price

        
        # Quantity is negative for out valuation layers.
        
        company_id = self.env.context.get('force_company', self.env.company.id)
        company = self.env['res.company'].browse(company_id)
        currency = company.currency_id
        quantity = -1 * quantity
        vals = {
            'product_id': self.id,
            'value': currency.round(quantity * manual_currency_rate ),
            'unit_cost': self.standard_price,
            'quantity': quantity,
        }
        fifo_vals = self._run_fifo(abs(quantity), company)
        vals['remaining_qty'] = fifo_vals.get('remaining_qty')
        # In case of AVCO, fix rounding issue of standard price when needed.
        if self.product_tmpl_id.cost_method == 'average' and not float_is_zero(self.quantity_svl, precision_rounding=self.uom_id.rounding):
            rounding_error = currency.round(
                (self.standard_price * self.quantity_svl - self.value_svl) * abs(quantity / self.quantity_svl)
            )
            if rounding_error:
                # If it is bigger than the (smallest number of the currency * quantity) / 2,
                # then it isn't a rounding error but a stock valuation error, we shouldn't fix it under the hood ...
                if abs(rounding_error) <= max((abs(quantity) * currency.rounding) / 2, currency.rounding):
                    vals['value'] += rounding_error
                    vals['rounding_adjustment'] = '\nRounding Adjustment: %s%s %s' % (
                        '+' if rounding_error > 0 else '',
                        float_repr(rounding_error, precision_digits=currency.decimal_places),
                        currency.symbol
                    )
        if self.product_tmpl_id.cost_method == 'fifo':
            vals.update(fifo_vals)
        return vals

class stock_move(models.Model):
    _inherit = 'stock.move'

    def _create_in_svl(self, forced_quantity=None):
        """Create a `stock.valuation.layer` from `self`.

        :param forced_quantity: under some circunstances, the quantity to value is different than
            the initial demand of the move (Default value = None)
        """
        rec = super(stock_move, self)._create_in_svl(forced_quantity=None)
        for rc in rec:
            for line in self:
                if line.purchase_line_id:
                    if line.purchase_line_id.order_id.purchase_manual_currency_rate_active:
                        price_unit = line.purchase_line_id.order_id.currency_id.round((line.purchase_line_id.price_unit))
                        rc.write({'unit_cost':line.purchase_line_id.price_unit*rc.quantity*line.purchase_line_id.order_id.purchase_manual_currency_rate,
                            'value': (price_unit * rc.quantity)*line.purchase_line_id.order_id.purchase_manual_currency_rate,
                            'remaining_value':(price_unit * rc.quantity)*line.purchase_line_id.order_id.purchase_manual_currency_rate })
        return rec

    def _generate_valuation_lines_data(self, partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description):
        """ Overridden from stock_account to support amount_currency on valuation lines generated from po
        """
        self.ensure_one()

        rslt = super(stock_move, self)._generate_valuation_lines_data(partner_id, qty, debit_value, credit_value, debit_account_id, credit_account_id, svl_id, description)
        purchase_currency = self.purchase_line_id.currency_id
        company_currency = self.company_id.currency_id
        if not self.purchase_line_id or purchase_currency == company_currency:
            return rslt
        svl = self.env['stock.valuation.layer'].browse(svl_id)
        if not svl.account_move_line_id:
            if self.purchase_line_id.order_id.purchase_manual_currency_rate_active:
                rslt['credit_line_vals']['amount_currency'] = rslt['credit_line_vals']['balance'] / self.purchase_line_id.order_id.purchase_manual_currency_rate
                rslt['debit_line_vals']['amount_currency'] =  rslt['debit_line_vals']['balance'] / self.purchase_line_id.order_id.purchase_manual_currency_rate
            else:
                rslt['credit_line_vals']['amount_currency'] = company_currency._convert(
                    rslt['credit_line_vals']['balance'],
                    purchase_currency,
                    self.company_id,
                    self.date
                )
                rslt['debit_line_vals']['amount_currency'] = company_currency._convert(
                    rslt['debit_line_vals']['balance'],
                    purchase_currency,
                    self.company_id,
                    self.date
                )
            rslt['debit_line_vals']['currency_id'] = purchase_currency.id
            rslt['credit_line_vals']['currency_id'] = purchase_currency.id
        else:
            rslt['credit_line_vals']['amount_currency'] = 0
            rslt['debit_line_vals']['amount_currency'] = 0
            rslt['debit_line_vals']['currency_id'] = purchase_currency.id
            rslt['credit_line_vals']['currency_id'] = purchase_currency.id
            if not svl.price_diff_value:
                return rslt
            # The idea is to force using the company currency during the reconciliation process
            rslt['debit_line_vals_curr'] = {
                'name': _("Currency exchange rate difference"),
                'product_id': self.product_id.id,
                'quantity': 0,
                'product_uom_id': self.product_id.uom_id.id,
                'partner_id': partner_id,
                'balance': 0,
                'account_id': debit_account_id,
                'currency_id': purchase_currency.id,
                'amount_currency': -svl.price_diff_value,
            }
            rslt['credit_line_vals_curr'] = {
                'name': _("Currency exchange rate difference"),
                'product_id': self.product_id.id,
                'quantity': 0,
                'product_uom_id': self.product_id.uom_id.id,
                'partner_id': partner_id,
                'balance': 0,
                'account_id': credit_account_id,
                'currency_id': purchase_currency.id,
                'amount_currency': svl.price_diff_value,
            }
        return rslt

    def _prepare_account_move_vals(self, credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost):
        res = super(stock_move, self)._prepare_account_move_vals(credit_account_id, debit_account_id, journal_id, qty, description, svl_id, cost)

        if self.purchase_line_id.order_id.purchase_manual_currency_rate_active:
            res.update({
                "manual_currency_rate_active": self.purchase_line_id.order_id.purchase_manual_currency_rate_active,
                "manual_currency_rate": self.purchase_line_id.order_id.purchase_manual_currency_rate,
                "currency_id": self.purchase_line_id.order_id.currency_id.id,
            })

        if self.sale_line_id.order_id.sale_manual_currency_rate_active:
            res.update({
                "manual_currency_rate_active": self.sale_line_id.order_id.sale_manual_currency_rate_active,
                "manual_currency_rate": self.sale_line_id.order_id.sale_manual_currency_rate,
                "currency_id": self.sale_line_id.order_id.currency_id.id,
            })

        return res

class account_invoice_line(models.Model):
    _inherit = 'account.move.line'

    @api.depends('product_id', 'product_uom_id')
    def _compute_price_unit(self):
        for line in self:
            manual_currency_rate_active = line.move_id.manual_currency_rate_active
            manual_currency_rate = line.move_id.manual_currency_rate
            if not line.product_id or line.display_type in ('line_section', 'line_note'):
                continue
            if line.move_id.is_sale_document(include_receipts=True):
                document_type = 'sale'
            elif line.move_id.is_purchase_document(include_receipts=True):
                document_type = 'purchase'
            else:
                document_type = 'other'
            line.price_unit = line.product_id.with_context(manual_currency_rate_active=manual_currency_rate_active,manual_currency_rate=manual_currency_rate)._get_tax_included_unit_price(
                line.move_id.company_id,
                line.move_id.currency_id,
                line.move_id.date,
                document_type,
                fiscal_position=line.move_id.fiscal_position_id,
                product_uom=line.product_uom_id,
            )

    @api.depends('currency_id', 'company_id', 'move_id.date', 
        'move_id.manual_currency_rate_active', 'move_id.manual_currency_rate')
    def _compute_currency_rate(self):
        @lru_cache()
        def get_rate(from_currency, to_currency, company, date):
            return self.env['res.currency']._get_conversion_rate(
                from_currency=from_currency,
                to_currency=to_currency,
                company=company,
                date=date,
            )
        for line in self:
            if line.move_id.manual_currency_rate_active:
                line.currency_rate = line.move_id.manual_currency_rate or 1.0
            else:
                line.currency_rate = get_rate(
                    from_currency=line.company_currency_id,
                    to_currency=line.currency_id,
                    company=line.company_id,
                    date=line.move_id.date or fields.Date.context_today(line),
                )

    @contextmanager
    def _sync_invoice(self, container):
        if container['records'].env.context.get('skip_invoice_line_sync'):
            yield
            return  # avoid infinite recursion

        def existing():
            return {
                line: {
                    'amount_currency': line.currency_id.round(line.amount_currency),
                    'balance': line.company_id.currency_id.round(line.balance),
                    'currency_rate': line.currency_rate,
                    'price_subtotal': line.currency_id.round(line.price_subtotal),
                    'move_type': line.move_id.move_type,
                } for line in container['records'].with_context(
                    skip_invoice_line_sync=True,
                ).filtered(lambda l: l.move_id.is_invoice(True))
            }

        def changed(fname):
            return line not in before or before[line][fname] != after[line][fname]

        before = existing()
        yield
        after = existing()
        for line in after:
            if (
                line.display_type == 'product'
                and (not changed('amount_currency') or line not in before)
            ):
                amount_currency = line.move_id.direction_sign * line.currency_id.round(line.price_subtotal)
                if line.amount_currency != amount_currency or line not in before:
                    line.amount_currency = amount_currency
                if line.currency_id == line.company_id.currency_id:
                    line.balance = amount_currency

        after = existing()
        for line in after:
            if line.move_id.manual_currency_rate_active == True:
                if (
                    (changed('amount_currency') or changed('currency_rate') or changed('move_type'))
                    and (not changed('balance') or (line not in before and not line.balance))
                ):
                    balance = line.company_id.currency_id.round(line.amount_currency * line.currency_rate)
                    line.balance = balance
            else:
                if (
                    (changed('amount_currency') or changed('currency_rate') or changed('move_type'))
                    and (not changed('balance') or (line not in before and not line.balance))
                ):
                    balance = line.company_id.currency_id.round(line.amount_currency / line.currency_rate)
                    line.balance = balance
        # Since this method is called during the sync, inside of `create`/`write`, these fields
        # already have been computed and marked as so. But this method should re-trigger it since
        # it changes the dependencies.
        self.env.add_to_compute(self._fields['debit'], container['records'])
        self.env.add_to_compute(self._fields['credit'], container['records'])
    
    @api.model
    def _prepare_reconciliation_single_partial(self, debit_values, credit_values, shadowed_aml_values=None):
        """ Prepare the values to create an account.partial.reconcile later when reconciling the dictionaries passed
        as parameters, each one representing an account.move.line.
        :param debit_values:  The values of account.move.line to consider for a debit line.
        :param credit_values: The values of account.move.line to consider for a credit line.
        :param shadowed_aml_values: A mapping aml -> dictionary to replace some original aml values to something else.
                                    This is usefull if you want to preview the reconciliation before doing some changes
                                    on amls like changing a date or an account.
        :return: A dictionary:
            * debit_values:     None if the line has nothing left to reconcile.
            * credit_values:    None if the line has nothing left to reconcile.
            * partial_values:   The newly computed values for the partial.
            * exchange_values:  The values to create an exchange difference linked to this partial.
        """
        # ==== Determine the currency in which the reconciliation will be done ====
        # In this part, we retrieve the residual amounts, check if they are zero or not and determine in which
        # currency and at which rate the reconciliation will be done.

        def get_odoo_rate(vals):
            if vals.get('manual_currency_rate'):
                exchange_rate = vals.get('manual_currency_rate')
                return exchange_rate

        res = {
            'debit_values': debit_values,
            'credit_values': credit_values,
        }
        
        if debit_values.get('record') and debit_values['record'].move_id.manual_currency_rate_active and debit_values['record'].move_id.manual_currency_rate:
            debit_values['manual_currency_rate'] = debit_values['record'].move_id.manual_currency_rate
        if credit_values.get('record') and credit_values['record'].move_id.manual_currency_rate_active and credit_values['record'].move_id.manual_currency_rate:
            credit_values['manual_currency_rate'] = credit_values['record'].move_id.manual_currency_rate
        

        debit_aml = debit_values['aml']
        credit_aml = credit_values['aml']
        debit_currency = debit_aml._get_reconciliation_aml_field_value('currency_id', shadowed_aml_values)
        credit_currency = credit_aml._get_reconciliation_aml_field_value('currency_id', shadowed_aml_values)
        company_currency = debit_aml.company_currency_id

        remaining_debit_amount_curr = debit_values['amount_residual_currency']
        remaining_credit_amount_curr = credit_values['amount_residual_currency']
        remaining_debit_amount = debit_values['amount_residual']
        remaining_credit_amount = credit_values['amount_residual']

        debit_available_residual_amounts = self._prepare_move_line_residual_amounts(
            debit_values,
            credit_currency,
            shadowed_aml_values=shadowed_aml_values,
            other_aml_values=credit_values,
        )
        credit_available_residual_amounts = self._prepare_move_line_residual_amounts(
            credit_values,
            debit_currency,
            shadowed_aml_values=shadowed_aml_values,
            other_aml_values=debit_values,
        )

        if debit_currency != company_currency \
            and debit_currency in debit_available_residual_amounts \
            and debit_currency in credit_available_residual_amounts:
            recon_currency = debit_currency
        elif credit_currency != company_currency \
            and credit_currency in debit_available_residual_amounts \
            and credit_currency in credit_available_residual_amounts:
            recon_currency = credit_currency
        else:
            recon_currency = company_currency

        debit_recon_values = debit_available_residual_amounts.get(recon_currency)
        credit_recon_values = credit_available_residual_amounts.get(recon_currency)

        # Check if there is something left to reconcile. Move to the next loop iteration if not.
        skip_reconciliation = False
        if not debit_recon_values:
            res['debit_values'] = None
            skip_reconciliation = True
        if not credit_recon_values:
            res['credit_values'] = None
            skip_reconciliation = True
        if skip_reconciliation:
            return res

        recon_debit_amount = debit_recon_values['residual']
        recon_credit_amount = -credit_recon_values['residual']

        # ==== Match both lines together and compute amounts to reconcile ====

        # Special case for exchange difference lines. In that case, both lines are sharing the same foreign
        # currency but at least one has no amount in foreign currency.
        # In that case, we don't want a rate for the opposite line because the exchange difference is supposed
        # to reduce only the amount in company currency but not the foreign one.
        exchange_line_mode = \
            recon_currency == company_currency \
            and debit_currency == credit_currency \
            and (
                not debit_available_residual_amounts.get(debit_currency)
                or not credit_available_residual_amounts.get(credit_currency)
            )

        # Determine which line is fully matched by the other.
        compare_amounts = recon_currency.compare_amounts(recon_debit_amount, recon_credit_amount)
        min_recon_amount = min(recon_debit_amount, recon_credit_amount)
        debit_fully_matched = compare_amounts <= 0
        credit_fully_matched = compare_amounts >= 0

        # ==== Computation of partial amounts ====
        if recon_currency == company_currency:
            if exchange_line_mode:
                debit_rate = None
                credit_rate = None
            else:
                debit_rate = debit_available_residual_amounts.get(debit_currency, {}).get('rate')
                credit_rate = credit_available_residual_amounts.get(credit_currency, {}).get('rate')

            # Compute the partial amount expressed in company currency.
            partial_amount = min_recon_amount

            # Compute the partial amount expressed in foreign currency.
            if debit_rate:
                partial_debit_amount_currency = debit_currency.round(debit_rate * min_recon_amount)
                partial_debit_amount_currency = min(partial_debit_amount_currency, remaining_debit_amount_curr)
            else:
                partial_debit_amount_currency = 0.0
            if credit_rate:
                partial_credit_amount_currency = credit_currency.round(credit_rate * min_recon_amount)
                partial_credit_amount_currency = min(partial_credit_amount_currency, -remaining_credit_amount_curr)
            else:
                partial_credit_amount_currency = 0.0

        else:
            # recon_currency != company_currency
            if exchange_line_mode:
                debit_rate = None
                credit_rate = None
            else:
                debit_rate = debit_recon_values['rate']
                credit_rate = credit_recon_values['rate']

            # Compute the partial amount expressed in foreign currency.
            if debit_rate:
                partial_debit_amount = company_currency.round(min_recon_amount / debit_rate)
                partial_debit_amount = min(partial_debit_amount, remaining_debit_amount)
            else:
                partial_debit_amount = 0.0
            if credit_rate:
                partial_credit_amount = company_currency.round(min_recon_amount / credit_rate)
                partial_credit_amount = min(partial_credit_amount, -remaining_credit_amount)
            else:
                partial_credit_amount = 0.0
            partial_amount = min(partial_debit_amount, partial_credit_amount)

            # Compute the partial amount expressed in foreign currency.
            # Take care to handle the case when a line expressed in company currency is mimicking the foreign
            # currency of the opposite line.
            if debit_currency == company_currency:
                partial_debit_amount_currency = partial_amount
            else:
                partial_debit_amount_currency = min_recon_amount
            if credit_currency == company_currency:
                partial_credit_amount_currency = partial_amount
            else:
                partial_credit_amount_currency = min_recon_amount

        # Computation of the partial exchange difference. You can skip this part using the
        # `no_exchange_difference` context key (when reconciling an exchange difference for example).
        if not self._context.get('no_exchange_difference'):
            exchange_lines_to_fix = self.env['account.move.line']
            amounts_list = []
            if recon_currency == company_currency:
                if debit_fully_matched:
                    debit_exchange_amount = remaining_debit_amount_curr - partial_debit_amount_currency
                    if not debit_currency.is_zero(debit_exchange_amount):
                        exchange_lines_to_fix += debit_aml
                        amounts_list.append({'amount_residual_currency': debit_exchange_amount})
                        remaining_debit_amount_curr -= debit_exchange_amount
                if credit_fully_matched:
                    credit_exchange_amount = remaining_credit_amount_curr + partial_credit_amount_currency
                    if not credit_currency.is_zero(credit_exchange_amount):
                        exchange_lines_to_fix += credit_aml
                        amounts_list.append({'amount_residual_currency': credit_exchange_amount})
                        remaining_credit_amount_curr += credit_exchange_amount

            else:
                if debit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    debit_exchange_amount = remaining_debit_amount - partial_amount
                    if not company_currency.is_zero(debit_exchange_amount):
                        exchange_lines_to_fix += debit_aml
                        amounts_list.append({'amount_residual': debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_currency == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    debit_exchange_amount = partial_debit_amount - partial_amount
                    if company_currency.compare_amounts(debit_exchange_amount, 0.0) > 0:
                        exchange_lines_to_fix += debit_aml
                        amounts_list.append({'amount_residual': debit_exchange_amount})
                        remaining_debit_amount -= debit_exchange_amount
                        if debit_currency == company_currency:
                            remaining_debit_amount_curr -= debit_exchange_amount

                if credit_fully_matched:
                    # Create an exchange difference on the remaining amount expressed in company's currency.
                    credit_exchange_amount = remaining_credit_amount + partial_amount
                    if not company_currency.is_zero(credit_exchange_amount):
                        exchange_lines_to_fix += credit_aml
                        amounts_list.append({'amount_residual': credit_exchange_amount})
                        remaining_credit_amount -= credit_exchange_amount
                        if credit_currency == company_currency:
                            remaining_credit_amount_curr -= credit_exchange_amount
                else:
                    # Create an exchange difference ensuring the rate between the residual amounts expressed in
                    # both foreign and company's currency is still consistent regarding the rate between
                    # 'amount_currency' & 'balance'.
                    credit_exchange_amount = partial_amount - partial_credit_amount
                    if company_currency.compare_amounts(credit_exchange_amount, 0.0) < 0:
                        exchange_lines_to_fix += credit_aml
                        amounts_list.append({'amount_residual': credit_exchange_amount})
                        remaining_credit_amount += credit_exchange_amount
                        if credit_currency == company_currency:
                            remaining_credit_amount_curr += credit_exchange_amount

            if exchange_lines_to_fix:
                res['exchange_values'] = exchange_lines_to_fix._prepare_exchange_difference_move_vals(
                    amounts_list,
                    exchange_date=max(
                        debit_aml._get_reconciliation_aml_field_value('date', shadowed_aml_values),
                        credit_aml._get_reconciliation_aml_field_value('date', shadowed_aml_values),
                    ),
                )

        # ==== Create partials ====

        remaining_debit_amount -= partial_amount
        remaining_credit_amount += partial_amount
        remaining_debit_amount_curr -= partial_debit_amount_currency
        remaining_credit_amount_curr += partial_credit_amount_currency

        res['partial_values'] = {
            'amount': partial_amount,
            'debit_amount_currency': partial_debit_amount_currency,
            'credit_amount_currency': partial_credit_amount_currency,
            'debit_move_id': debit_aml.id,
            'credit_move_id': credit_aml.id,
        }

        debit_values['amount_residual'] = remaining_debit_amount
        debit_values['amount_residual_currency'] = remaining_debit_amount_curr
        credit_values['amount_residual'] = remaining_credit_amount
        credit_values['amount_residual_currency'] = remaining_credit_amount_curr

        if recon_currency.is_zero(recon_debit_amount) or debit_fully_matched:
            res['debit_values'] = None
        if recon_currency.is_zero(recon_credit_amount) or credit_fully_matched:
            res['credit_values'] = None

        return res

    def _generate_price_difference_vals(self, layers):
        """
        The method will determine which layers are impacted by the AML (`self`) and, in case of a price difference, it
        will then return the values of the new AMLs and SVLs
        """
        self.ensure_one()
        po_line = self.purchase_line_id
        product_uom = self.product_id.uom_id

        # `history` is a list of tuples: (time, aml, layer)
        # aml and layer will never be both defined
        # we use this to get an order between posted AML and layers
        history = [(layer.create_date, False, layer) for layer in layers]
        am_state_field = self.env['ir.model.fields'].search([('model', '=', 'account.move'), ('name', '=', 'state')], limit=1)
        for aml in po_line.invoice_lines:
            move = aml.move_id
            if move.state != 'posted':
                continue
            state_trackings = move.message_ids.tracking_value_ids.filtered(lambda t: t.field_id == am_state_field).sorted('id')
            time = state_trackings[-1:].create_date or move.create_date  # `or` in case it has been created in posted state
            history.append((time, aml, False))
        # Sort history based on the datetime. In case of equality, the prority is given to SVLs, then to IDs.
        # That way, we ensure a deterministic behaviour
        history.sort(key=lambda item: (item[0], bool(item[1]), (item[1] or item[2]).id))

        # the next dict is a matrix [layer L, invoice I] where each cell gives two info:
        # [initial qty of L invoiced by I, remaining invoiced qty]
        # the second info is usefull in case of a refund
        layers_and_invoices_qties = defaultdict(lambda: [0, 0])

        # the next dict will also provide two info:
        # [total qty to invoice, remaining qty to invoice]
        # we need the total qty to invoice, so we will be able to deduce the invoiced qty before `self`
        qty_to_invoice_per_layer = defaultdict(lambda: [0, 0])

        # Replay the whole history: we want to know what are the links between each layer and each invoice,
        # and then the links between `self` and the layers
        history.append((False, self, False))  # time was only usefull for the sorting
        for _time, aml, layer in history:
            if layer:
                total_layer_qty_to_invoice = abs(layer.quantity)
                initial_layer = layer.stock_move_id.origin_returned_move_id.stock_valuation_layer_ids
                if initial_layer:
                    # `layer` is a return. We will cancel the qty to invoice of the returned layer
                    # /!\ we will cancel the qty not yet invoiced only
                    initial_layer_remaining_qty = qty_to_invoice_per_layer[initial_layer][1]
                    common_qty = min(initial_layer_remaining_qty, total_layer_qty_to_invoice)
                    qty_to_invoice_per_layer[initial_layer][0] -= common_qty
                    qty_to_invoice_per_layer[initial_layer][1] -= common_qty
                    total_layer_qty_to_invoice = max(0, total_layer_qty_to_invoice - common_qty)
                if float_compare(total_layer_qty_to_invoice, 0, precision_rounding=product_uom.rounding) > 0:
                    qty_to_invoice_per_layer[layer] = [total_layer_qty_to_invoice, total_layer_qty_to_invoice]
            else:
                invoice = aml.move_id
                impacted_invoice = False
                aml_qty = aml.product_uom_id._compute_quantity(aml.quantity, product_uom)
                if aml.is_refund:
                    reversed_invoice = aml.move_id.reversed_entry_id
                    if reversed_invoice:
                        sign = -1
                        impacted_invoice = reversed_invoice
                        # it's a refund, therefore we can only consume the quantities invoiced by
                        # the initial invoice (`reversed_invoice`)
                        layers_to_consume = []
                        for layer in layers:
                            remaining_invoiced_qty = layers_and_invoices_qties[(layer, reversed_invoice)][1]
                            layers_to_consume.append((layer, remaining_invoiced_qty))
                    else:
                        # the refund has been generated because of a stock return, let's find and use it
                        sign = 1
                        layers_to_consume = []
                        for layer in qty_to_invoice_per_layer:
                            if layer.stock_move_id._is_out():
                                layers_to_consume.append((layer, qty_to_invoice_per_layer[layer][1]))
                else:
                    # classic case, we are billing a received quantity so let's use the incoming SVLs
                    sign = 1
                    layers_to_consume = []
                    for layer in qty_to_invoice_per_layer:
                        if layer.stock_move_id._is_in():
                            layers_to_consume.append((layer, qty_to_invoice_per_layer[layer][1]))
                while float_compare(aml_qty, 0, precision_rounding=product_uom.rounding) > 0 and layers_to_consume:
                    layer, total_layer_qty_to_invoice = layers_to_consume[0]
                    layers_to_consume = layers_to_consume[1:]
                    if float_is_zero(total_layer_qty_to_invoice, precision_rounding=product_uom.rounding):
                        continue
                    common_qty = min(aml_qty, total_layer_qty_to_invoice)
                    aml_qty -= common_qty
                    qty_to_invoice_per_layer[layer][1] -= sign * common_qty
                    layers_and_invoices_qties[(layer, invoice)] = [common_qty, common_qty]
                    layers_and_invoices_qties[(layer, impacted_invoice)][1] -= common_qty

        # Now we know what layers does `self` use, let's check if we have to create a pdiff SVL
        # (or cancel such an SVL in case of a refund)
        invoice = self.move_id
        svl_vals_list = []
        aml_vals_list = []
        for layer in layers:
            # use the link between `self` and `layer` (i.e. the qty of `layer` billed by `self`)
            invoicing_layer_qty = layers_and_invoices_qties[(layer, invoice)][1]
            if float_is_zero(invoicing_layer_qty, precision_rounding=product_uom.rounding):
                continue
            # We will only consider the total quantity to invoice of the layer because we don't
            # want to invoice a part of the layer that has not been invoiced and that has been
            # returned in the meantime
            total_layer_qty_to_invoice = qty_to_invoice_per_layer[layer][0]
            remaining_qty = layer.remaining_qty
            out_layer_qty = total_layer_qty_to_invoice - remaining_qty
            if self.is_refund:
                sign = -1
                reversed_invoice = invoice.reversed_entry_id
                if not reversed_invoice:
                    # this is a refund for a returned quantity, we don't have anything to do
                    continue
                initial_invoiced_qty = layers_and_invoices_qties[(layer, reversed_invoice)][0]
                initial_pdiff_svl = layer.stock_valuation_layer_ids.filtered(lambda svl: svl.account_move_line_id.move_id == reversed_invoice)
                if not initial_pdiff_svl or float_is_zero(initial_invoiced_qty, precision_rounding=product_uom.rounding):
                    continue
                # We have an already-out quantity: we must skip the part already invoiced. So, first,
                # let's compute the already invoiced quantity...
                previously_invoiced_qty = 0
                for item in history:
                    previous_aml = item[1]
                    if not previous_aml or previous_aml.is_refund:
                        continue
                    previous_invoice = previous_aml.move_id
                    if previous_invoice == reversed_invoice:
                        break
                    previously_invoiced_qty += layers_and_invoices_qties[(layer, previous_invoice,)][1]
                # ... Second, skip it:
                out_qty_to_invoice = max(0, out_layer_qty - previously_invoiced_qty)
                qty_to_correct = max(0, invoicing_layer_qty - out_qty_to_invoice)
                if out_qty_to_invoice:
                    # In case the out qty is different from the one posted by the initial bill, we should compensate
                    # this quantity with debit/credit between stock_in and expense, but we are reversing an initial
                    # invoice and don't want to do more than the original one
                    out_qty_to_invoice = 0
                aml = initial_pdiff_svl.account_move_line_id
                parent_layer = initial_pdiff_svl.stock_valuation_layer_id
                layer_price_unit = parent_layer._get_layer_price_unit()
            else:
                sign = 1
                # get the invoiced qty of the layer without considering `self`
                invoiced_layer_qty = total_layer_qty_to_invoice - qty_to_invoice_per_layer[layer][1] - invoicing_layer_qty
                remaining_out_qty_to_invoice = max(0, out_layer_qty - invoiced_layer_qty)
                out_qty_to_invoice = min(remaining_out_qty_to_invoice, invoicing_layer_qty)
                qty_to_correct = invoicing_layer_qty - out_qty_to_invoice
                layer_price_unit = layer._get_layer_price_unit()


                returned_move = layer.stock_move_id.origin_returned_move_id
                if returned_move and returned_move._is_out() and returned_move._is_returned(valued_type='out'):
                    # Odd case! The user receives a product, then returns it. The returns are processed as classic
                    # output, so the value of the returned product can be different from the initial one. The user
                    # then receives again the returned product (that's where we are here) -> the SVL is based on
                    # the returned one, the accounting entries are already compensated, and we don't want to impact
                    # the stock valuation. So, let's fake the layer price unit with the POL one as everything is
                    # already ok
                    layer_price_unit = po_line._get_gross_price_unit()

                aml = self

            aml_gross_price_unit = aml._get_gross_unit_price()
            # convert from aml currency to company currency
            aml_price_unit = aml_gross_price_unit * aml.currency_rate
            aml_price_unit = aml.product_uom_id._compute_price(aml_price_unit, product_uom)

            unit_valuation_difference = aml_price_unit - layer_price_unit

            # Generate the AML values for the already out quantities
            # convert from company currency to aml currency
            unit_valuation_difference_curr = unit_valuation_difference * self.currency_rate
            unit_valuation_difference_curr = product_uom._compute_price(unit_valuation_difference_curr, self.product_uom_id)
            out_qty_to_invoice = product_uom._compute_quantity(out_qty_to_invoice, self.product_uom_id)
            if not float_is_zero(unit_valuation_difference_curr * out_qty_to_invoice, precision_rounding=self.currency_id.rounding):
                aml_vals_list += self._prepare_pdiff_aml_vals(out_qty_to_invoice, unit_valuation_difference_curr)

            # Generate the SVL values for the on hand quantities (and impact the parent layer)
            po_pu_curr = po_line.currency_id._convert(po_line.price_unit, self.currency_id, self.company_id, self.move_id.invoice_date or self.date or fields.Date.context_today(self), round=False)
            price_difference_curr = po_pu_curr - aml_gross_price_unit
            if not float_is_zero(unit_valuation_difference * qty_to_correct, precision_rounding=self.company_id.currency_id.rounding):
                svl_vals = self._prepare_pdiff_svl_vals(layer, sign * qty_to_correct, unit_valuation_difference, price_difference_curr)
                layer.remaining_value += svl_vals['value']
                svl_vals_list.append(svl_vals)
        return svl_vals_list, aml_vals_list

class account_invoice(models.Model):
    _inherit = 'account.move'

    manual_currency_rate_active = fields.Boolean('Apply Manual Exchange')
    manual_currency_rate = fields.Float('Rate', digits=(12, 6))

    @api.constrains("manual_currency_rate")
    def _check_manual_currency_rate(self):
        for record in self:
            if record.manual_currency_rate_active:
                if record.manual_currency_rate == 0:
                    raise UserError(
                        _('Exchange Rate Field is required , Please fill that.'))

    @api.onchange('manual_currency_rate_active', 'currency_id')
    def check_currency_id(self):
        if self.manual_currency_rate_active:
            if self.currency_id == self.company_id.currency_id:
                self.manual_currency_rate_active = False
                raise UserError(
                    _('Company currency and invoice currency same, You can not add manual Exchange rate for same currency.'))

    
    def _compute_payments_widget_to_reconcile_info(self):
        for move in self:
            move.invoice_outstanding_credits_debits_widget = False
            move.invoice_has_outstanding = False

            if move.state != 'posted' \
                    or move.payment_state not in ('not_paid', 'partial') \
                    or not move.is_invoice(include_receipts=True):
                continue

            pay_term_lines = move.line_ids\
                .filtered(lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable'))

            domain = [
                ('account_id', 'in', pay_term_lines.account_id.ids),
                ('parent_state', '=', 'posted'),
                ('partner_id', '=', move.commercial_partner_id.id),
                ('reconciled', '=', False),
                '|', ('amount_residual', '!=', 0.0), ('amount_residual_currency', '!=', 0.0),
            ]

            payments_widget_vals = {'outstanding': True, 'content': [], 'move_id': move.id}

            if move.is_inbound():
                domain.append(('balance', '<', 0.0))
                payments_widget_vals['title'] = _('Outstanding credits')
            else:
                domain.append(('balance', '>', 0.0))
                payments_widget_vals['title'] = _('Outstanding debits')

            for line in self.env['account.move.line'].search(domain):

                if line.currency_id == move.currency_id:
                    # Same foreign currency.
                    amount = abs(line.amount_residual_currency)
                else:
                    # Different foreign currencies.
                    if move.manual_currency_rate_active and move.manual_currency_rate:
                        amount = abs(line.amount_residual) * move.manual_currency_rate
                    else:
                        amount = line.company_currency_id._convert(
                            abs(line.amount_residual),
                            move.currency_id,
                            move.company_id,
                            line.date,
                        )

                if move.currency_id.is_zero(amount):
                    continue

                payments_widget_vals['content'].append({
                    'journal_name': line.ref or line.move_id.name,
                    'amount': amount,
                    'currency_id': move.currency_id.id,
                    'id': line.id,
                    'move_id': line.move_id.id,
                    'date': fields.Date.to_string(line.date),
                    'account_payment_id': line.payment_id.id,
                })

            if not payments_widget_vals['content']:
                continue

            move.invoice_outstanding_credits_debits_widget = payments_widget_vals
            move.invoice_has_outstanding = True

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _get_tax_included_unit_price(self, company, currency, document_date, document_type,
            is_refund_document=False, product_uom=None, product_currency=None,
            product_price_unit=None, product_taxes=None, fiscal_position=None
        ):
        """ Helper to get the price unit from different models.
            This is needed to compute the same unit price in different models (sale order, account move, etc.) with same parameters.
        """

        product = self

        assert document_type

        if product_uom is None:
            product_uom = product.uom_id
        if not product_currency:
            if document_type == 'sale':
                product_currency = product.currency_id
            elif document_type == 'purchase':
                product_currency = company.currency_id
        if product_price_unit is None:
            if document_type == 'sale':
                product_price_unit = product.with_company(company).lst_price
            elif document_type == 'purchase':
                product_price_unit = product.with_company(company).standard_price
            else:
                return 0.0
        if product_taxes is None:
            if document_type == 'sale':
                product_taxes = product.taxes_id.filtered(lambda x: x.company_id == company)
            elif document_type == 'purchase':
                product_taxes = product.supplier_taxes_id.filtered(lambda x: x.company_id == company)
        # Apply unit of measure.
        if product_uom and product.uom_id != product_uom:
            product_price_unit = product.uom_id._compute_price(product_price_unit, product_uom)
        # Apply fiscal position.
        if product_taxes and fiscal_position:
            product_taxes_after_fp = fiscal_position.map_tax(product_taxes)
            flattened_taxes_after_fp = product_taxes_after_fp._origin.flatten_taxes_hierarchy()
            flattened_taxes_before_fp = product_taxes._origin.flatten_taxes_hierarchy()
            taxes_before_included = all(tax.price_include for tax in flattened_taxes_before_fp)

            if set(product_taxes.ids) != set(product_taxes_after_fp.ids) and taxes_before_included:
                taxes_res = flattened_taxes_before_fp.compute_all(
                    product_price_unit,
                    quantity=1.0,
                    currency=currency,
                    product=product,
                    is_refund=is_refund_document,
                )
                product_price_unit = taxes_res['total_excluded']
                if any(tax.price_include for tax in flattened_taxes_after_fp):
                    taxes_res = flattened_taxes_after_fp.compute_all(
                        product_price_unit,
                        quantity=1.0,
                        currency=currency,
                        product=product,
                        is_refund=is_refund_document,
                        handle_price_include=False,
                    )
                    for tax_res in taxes_res['taxes']:
                        tax = self.env['account.tax'].browse(tax_res['id'])
                        if tax.price_include:
                            product_price_unit += tax_res['amount']

        manual_currency_rate_active = self._context.get('manual_currency_rate_active')
        manual_currency_rate = self._context.get('manual_currency_rate')

        if currency != product_currency:
            if manual_currency_rate_active:
                product_price_unit = product_price_unit * manual_currency_rate
            else:
                product_price_unit = product_currency._convert(product_price_unit, currency, company, document_date)

        return product_price_unit