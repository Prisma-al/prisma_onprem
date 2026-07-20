/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {PosOrder} from "@point_of_sale/app/models/pos_order";
import { pick } from "@web/core/utils/objects";

import {PosStore} from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    getReceiptHeaderData(order) {
        const result = super.getReceiptHeaderData(...arguments);
        if (!order) {
            return result;
        }

        if (order && !order.fiscData) {
            this.getOrderData(order)
        }

        const partner = order.get_partner();
        if (partner) {
            result.partner = pick(
                partner,
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


patch(PosOrder.prototype, {
    createQrImage(profisc_qr_code) {
        const codeWriter = new window.ZXing.BrowserQRCodeSvgWriter();
        let qr_code_svg = new XMLSerializer().serializeToString(codeWriter.write(profisc_qr_code, 150, 150));
        return 'data:image/svg+xml;base64,' + window.btoa(qr_code_svg);
    },
    export_for_printing() {
        // Call the original method and get the result
        var result = super.export_for_printing(...arguments);
        let order = this;

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
