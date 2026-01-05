odoo.define('em_pos_open_cash_drawer', function (require) {
"use strict";

    const { useListener } = require('web.custom_hooks');
    const ProductScreen = require('point_of_sale.ProductScreen');
    const Registries = require('point_of_sale.Registries');
    const PaymentScreen = require('point_of_sale.PaymentScreen');


    const PosResProductScreen = (ProductScreen) =>
        class extends ProductScreen {
            constructor() {
                super(...arguments);
                useListener('click-open-cashbox', this._openCashDrawer);
            }

            async _openCashDrawer() {         	
                $("<center><div id='content_id'>Open Cash Drawer</div></center>").print();
            }
        }

    Registries.Component.extend(ProductScreen, PosResProductScreen);

    const PaymentScreen2 = (PaymentScreen) =>
    class extends PaymentScreen {
        new_js_cashdrawer() {
            var self = this;
            $("<center><div id='content_id'>Open Cash Drawer</div></center>").print();
        }
    }
    Registries.Component.extend(PaymentScreen, PaymentScreen2);
});

