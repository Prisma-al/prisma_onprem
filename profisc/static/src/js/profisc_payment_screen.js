/** @odoo-module **/

import {ErrorPopup} from "@point_of_sale/app/errors/popups/error_popup";
import {PaymentScreen} from "@point_of_sale/app/screens/payment_screen/payment_screen";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import {useService} from "@web/core/utils/hooks";

patch(PaymentScreen.prototype, {

    setup() {
        super.setup();
        this.pos = usePos();
        this.popup = useService("popup");
        console.log('df', this)
        let pmt_mthods = this.pos.payment_methods;
        const order = this.pos.get_order();
        let profisc_fisc_type = parseInt(order.profisc_fisc_type);


        /*
                 if the payment method has  is_cash_count equals to true it means that this is a cash payment or noncash method
                 if the payment method has  is_cash_count equals to false it means that this is a noncash payment method
                 in case that the user has chosen 'F.Kontrolli' show all payment methods
                 The difference between 0 and 3 is that the option 0 allows sending to Profisc whereas option 3 only allow showing multiple payment methods but doesn't allow sending to Profisc
         */

        if (profisc_fisc_type === 2) {
            this.payment_methods_from_config = pmt_mthods.filter(p => !p.is_cash_count);
        } else {
            this.payment_methods_from_config = pmt_mthods;
        }
        console.log("Entered ProfiscPaymentScreen constructor", this.payment_methods_from_config);

    },
    async validateOrder(isForceValidate) {
        // Custom validation logic.
        const order = this.pos.get_order();
        if (this._custom_validation_method(order)) {
            return super.validateOrder(...arguments);
        } else {
            return false;
        }
    },

    _custom_validation_method(order) {
        let order_lines = order.get_orderlines();
        let pmt_lines = order.get_paymentlines();
        let cash_count_nr = 0;
        let non_cash_count_nr = 0;
        let has_zero_qty = 0;
        let profisc_fisc_type = parseInt(order.profisc_fisc_type);

        // console.log({order_lines})
        order_lines.map(ol => {
            if (ol.quantity === 0) {
                has_zero_qty++;
            }
        });
        pmt_lines.map(p => {
            if (p.payment_method.is_cash_count) {
                cash_count_nr += 1;
            } else {
                non_cash_count_nr += 1;
            }
        });
        if (has_zero_qty > 0) {
            this.popup.add(ErrorPopup, {
                title: _t('Produkte me sasi 0'),
                body: _t('Error: One or more products has quantity = 0'),
            });
            return false;
        }

        if (cash_count_nr > 0 && non_cash_count_nr) {
            this.popup.add(ErrorPopup, {
                title: _t('Multiple payment methods type'),
                body: _t('Error: You must select only one payment method type, cash or noncash not both of them'),
            });
            return false;
        }

        let selected_partner = order.partner;
        // console.log({order, selected_partner})

        if (profisc_fisc_type === 2) {
            if (!selected_partner || selected_partner.profisc_customer_vat_type !== "9923") {
                this.popup.add(ErrorPopup, {
                    title: _t('Invalid Customer'),
                    body: _t('Error: In order to make an Electronic Invoice, you must select a valid customer'),
                });
                return false;
            }
        }

        if (selected_partner && selected_partner.profisc_customer_vat_type === "9923") {
            let is_valid_nuis = this.validateNUIS(selected_partner.vat);
            if (!is_valid_nuis) {
                this.popup.add(ErrorPopup, {
                    title: _t('Invalid NUIS'),
                    body: _t('Error: The selected customer\'s vat_type is NUIS, so it\'s required to have a valid NUIS in vat field'),
                });
                return false;
            }
        }
        return true; // duhet true
    },

    validateNUIS(str) {
        const regex = /^[A-Za-z]\d{8}[A-Za-z]$/;
        return regex.test(str);
    }

});
