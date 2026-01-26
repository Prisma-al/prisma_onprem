/** @odoo-module **/

import { Order } from "@point_of_sale/app/store/models";
import { patch } from "@web/core/utils/patch";

// Extend the Order model to add custom methods or properties
Order.prototype.set_bkt_data = function(data) {
    this.profisc_bkt_status = data.profisc_bkt_status || null;
    this.profisc_bkt_paymentType = data.profisc_bkt_paymentType || null;
    this.profisc_bkt_amount = data.profisc_bkt_amount || null;
    this.profisc_bkt_source = data.profisc_bkt_source || null;
    this.profisc_bkt_paymentMethod = data.profisc_bkt_paymentMethod || null;
};

Order.prototype.get_bkt_data = function() {
    return {
        profisc_bkt_status: this.profisc_bkt_status || null,
        profisc_bkt_paymentType: this.profisc_bkt_paymentType || null,
        profisc_bkt_amount: this.profisc_bkt_amount || null,
        profisc_bkt_source: this.profisc_bkt_source || null,
        profisc_bkt_paymentMethod: this.profisc_bkt_paymentMethod || null,
    };
};

patch(Order.prototype, {
    export_for_printing() {
        const data = super.export_for_printing();
        let order = this;

        // Add custom fields to the data object
        data.profisc_bkt_status = order?.profisc_bkt_status || null;
        data.profisc_bkt_paymentType = order?.profisc_bkt_paymentType || null;
        data.profisc_bkt_amount = order?.profisc_bkt_amount || null;
        data.profisc_bkt_source = order?.profisc_bkt_source || null;
        data.profisc_bkt_paymentMethod = order?.profisc_bkt_paymentMethod || null;

        return data;
    },
});