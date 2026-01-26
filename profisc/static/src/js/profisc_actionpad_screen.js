/** @odoo-module */

import {useRef} from "@odoo/owl";
import {ActionpadWidget} from "@point_of_sale/app/screens/product_screen/action_pad/action_pad";
import {patch} from "@web/core/utils/patch";
import {useService} from "@web/core/utils/hooks";

patch(ActionpadWidget.prototype, {
    setup() {
        // Call super.setup() first
        super.setup();
        console.log("Rendered: ProfiscActionpadWidgetScreen");
        this.orm = useService("orm");
        this.pos = usePos();
        // Initialize and check visibility
        this.setProfiscType();
        this._checkVisibility();
    },
    mounted() {
        // Attach the change event listener after the component is mounted
        const dropdown = useRef('changeFiscType');
        if (dropdown) {
            dropdown.addEventListener('change', this.changeFiscType.bind(this));
        } else {
            console.error('Dropdown not found');
        }
    },
    willUnmount() {
        // Clean up the event listener to avoid memory leaks
        const dropdown = useRef('changeFiscType');
        if (dropdown) {
            dropdown.removeEventListener('change', this.changeFiscType.bind(this));
        }
    },
    setProfiscType(type = "0") {
        const order = this.pos.get_order();
        if (order) {
            order.profisc_fisc_type = type;
        }
    },

    async _checkVisibility() {
        const currentCompanyId = this.env.services.company.currentCompany.id;
        console.log({currentCompanyId})

        const result = await this.orm.searchRead(
            'res.company', [["id", "=", currentCompanyId]], ['profisc_manual_fisc_select']
        );

        console.log({result})

        if (result.length > 0) {
            const companyData = result[0];
            if (companyData.profisc_manual_fisc_select) {
                document.querySelector('.profisc-payment-fiscalization').style.display = 'block';
            } else {
                this.setProfiscType("0");
                document.querySelector('.profisc-payment-fiscalization').style.display = 'none';
            }
        }
    },

    changeFiscType() {
        const dropdown = useRef('changeFiscType');
        const selectedValue = dropdown.options[dropdown.selectedIndex].value;
        this.env.pos.fiscType = selectedValue;

        const order = this.pos.get_order();
        if (order) {
            order.profisc_fisc_type = selectedValue;
        }
    },

});

ActionpadWidget.addControlButton({ component: SetSaleOrderButton });

ActionpadWidget.template = 'ProfiscActionpadWidgetScreen';
