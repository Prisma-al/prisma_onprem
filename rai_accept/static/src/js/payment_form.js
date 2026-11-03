/** @odoo-module */

import { PaymentForm } from '@payment/static/src/interactions/payment_form';
import { patch } from "@web/core/utils/patch";

patch(PaymentForm.prototype, {
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode === 'rai_accept') {
            // Use window.location.href instead of form.submit() because the redirect URL
            // contains query parameters that would be stripped by GET form submission.
            const div = document.createElement('div');
            div.innerHTML = processingValues['redirect_form_html'];
            const form = div.querySelector('form');
            if (form) {
                const params = new URLSearchParams(new FormData(form));
                window.top.location.href = form.getAttribute('action') + '?' + params.toString();
                return;
            }
        }
        super._processRedirectFlow(...arguments);
    }
});