/** @odoo-module */
import {ListController} from "@web/views/list/list_controller";
import {registry} from '@web/core/registry';
import {listView} from '@web/views/list/list_view';

export class PurchaseBookController extends ListController {
    setup() {
        super.setup();
    }

    getPurchaseBooks() {
        this.actionService.doAction({
            type: 'ir.actions.act_window',
            res_model: 'profisc.purchase_wizard',
            name: 'Get Purchase Invoices from Profisc',
            view_mode: 'form',
            view_type: 'form',
            views: [[false, 'form']],
            target: 'new',
            res_id: false,
        });
    }
}



registry.category("views").add("button_in_tree_purchase", {
    ...listView,
    Controller: PurchaseBookController,
    buttonTemplate: "button_sale.ListView.ButtonsPurchase",
});