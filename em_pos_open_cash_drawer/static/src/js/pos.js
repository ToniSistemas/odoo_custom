/** @odoo-module */

import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";

patch(ProductScreen.prototype, {
    async _openCashDrawer() {
        $("<center><div id='content_id'>Open Cash Drawer</div></center>").print();
    }
});

patch(PaymentScreen.prototype, {
    new_js_cashdrawer() {
        $("<center><div id='content_id'>Open Cash Drawer</div></center>").print();
    }
});

