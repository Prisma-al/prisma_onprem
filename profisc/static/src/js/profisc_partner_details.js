/** @odoo-module */


import {patch} from "@web/core/utils/patch";
import {PartnerDetailsEdit} from "@point_of_sale/app/screens/partner_list/partner_editor/partner_editor";

patch(PartnerDetailsEdit.prototype, {
    setup() {
        super.setup()
        const partner = this.props.partner;

        console.log({partner})
        this.changes.profisc_customer_vat_type = partner.profisc_customer_vat_type || ''
    },

    async saveChanges() {
        if (
            (!this.props.partner.profisc_customer_vat_type && !this.changes.profisc_customer_vat_type) ||
            this.changes.profisc_customer_vat_type === ""
        ) {
            this.changes.profisc_customer_vat_type = 'ID'
        }

        await super.saveChanges();
    },
})