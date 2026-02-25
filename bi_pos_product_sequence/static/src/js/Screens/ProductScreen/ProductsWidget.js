/** @odoo-module */

import { ProductsWidget } from "@point_of_sale/app/screens/product_screen/product_list/product_list";
import { patch } from "@web/core/utils/patch";

patch(ProductsWidget.prototype, {
    get productsToDisplay() {
        const products_data = super.productsToDisplay;
        const seq_zero = [];
        const seq_gr_zero = [];

        products_data.forEach((pro) => {
            if (pro.product_sequence == 0) {
                seq_zero.push(pro);
            } else if (pro.product_sequence > 0) {
                seq_gr_zero.push(pro);
            }
        });

        seq_gr_zero.sort((a, b) => a.product_sequence - b.product_sequence);
        
        return seq_gr_zero.concat(seq_zero);
    },
});
