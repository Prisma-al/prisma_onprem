/** @odoo-module */
import {ListController} from "@web/views/list/list_controller";
import {registry} from '@web/core/registry';
import {listView} from '@web/views/list/list_view';

export class PurchaseListController extends ListController {
    setup() {
        super.setup();
    }

    getPurchaseInvoices() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'profisc.invoice_wizard',
            name: 'Get Sale Invoices from Profisc',
            view_mode: 'form',
            view_type: 'form',
            views: [[false, 'form']],
            target: 'new',
            res_id: false,
        });
    }
}

registry.category("views").add("button_in_tree", {
    ...listView,
    Controller: PurchaseListController,
    buttonTemplate: "button_sale.ListView.Buttons",
});
