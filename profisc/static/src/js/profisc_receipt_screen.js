/** @odoo-module **/

import { ReceiptScreen } from "@point_of_sale/app/screens/receipt_screen/receipt_screen";
import { patch } from "@web/core/utils/patch";
import {usePos} from "@point_of_sale/app/store/pos_hook";
import { rpc } from "@web/core/network/rpc";

patch(ReceiptScreen.prototype, {
    setup() {
        super.setup();
        this.pos = usePos();
        console.log("🧩 ReceiptScreen patched successfully!");
    },

    async updateBKTFields() {
        console.log("Update BKT Fields clicked", this.currentOrder);
        const order = this.pos.get_order();
        const iic = order.fiscData.profisc_iic;

        console.log("Update order", order);

        const company = this.pos.company.id


        console.log("Update order", company);

        if (!iic) {
            console.warn("Order not yet fiscalised");
            return;
        }

        try {
            const result = await rpc('/pos/get_bkt_status',
                {
                    iic: iic,
                    company_id: company
                });

            order.set_bkt_data(result);
            console.log({result})
        } catch (e) {
            console.error("RPC call failed", e);
        }
    },
});
