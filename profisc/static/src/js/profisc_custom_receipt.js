/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {Order} from "@point_of_sale/app/store/models";
import { pick } from "@web/core/utils/objects";

import {PosStore} from "@point_of_sale/app/store/pos_store";

patch(PosStore.prototype, {
    getReceiptHeaderData(order) {
        console.log("order_fisc", order)
        console.log("order.partner_id", order.partner)

        const result = super.getReceiptHeaderData(...arguments);
        if (!order) {
            return result;
        }

        if (order && !order.fiscData) {
            this.getOrderData(order)
        }

        if(order.partner){
            result.partner = pick(
            order.partner,
            "name",
            "vat",
            "address",
            "city",
            "phone"
            );
        }


        return result;

    },
    getOrderData(order) {
        this.env.services.orm.call('pos.order', 'get_invoice', [order.name])
            .then((result) => {
                order.fiscData = result;
                console.log({order})
            })
            .catch((error) => {
                console.error("Error:", error);
            });


    }
});


patch(Order.prototype, {
    createQrImage(profisc_qr_code) {
        const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
        let qr_code_svg = new XMLSerializer().serializeToString(codeWriter.write(profisc_qr_code, 150, 150));
        return 'data:image/svg+xml;base64,' + window.btoa(qr_code_svg);
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        console.log({json})
    },
    export_for_printing() {
        // Call the original method and get the result
        var result = super.export_for_printing(...arguments);
        let order = this.pos.get_order();

        if (!order.fiscData) {
            this.pos.getOrderData(order); // Ensure ticket data is fetched if missing
        }
        console.log("order", order)

        result.profisc_iic = order.fiscData?.profisc_iic
        result.profisc_fic = order.fiscData?.profisc_fic
        result.profisc_eic = order.fiscData?.profisc_eic
        result.profisc_ubl_id = order.fiscData?.profisc_ubl_id
        result.profisc_fic_error_code = order.fiscData?.profisc_fic_error_code
        result.profisc_fic_error_description = order.fiscData?.profisc_fic_error_description
        result.profisc_qr_code = order.fiscData?.profisc_qr_code

        if (!result.profisc_fic) {
            result.profisc_fic = "Statusi i Faturës referuar Ligjit do të bëhet e ditur jo më vonë se 48 orë nga koha e lëshimit! Ju lutem, provoni përsëri me vonë."
        }
        if (result.profisc_qr_code) {
            result.qrCode = this.createQrImage(result.profisc_qr_code)
        }

        return result;
    },

    wait_for_push_order() {
        var result = super.wait_for_push_order(...arguments);
        result = Boolean(result);
        return result;
    },
});
