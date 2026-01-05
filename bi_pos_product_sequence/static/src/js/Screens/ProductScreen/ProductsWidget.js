odoo.define('bi_pos_product_sequence.BiProductsWidget', function(require) {
	"use strict";

	const ProductsWidget = require('point_of_sale.ProductsWidget');
	const PosComponent = require('point_of_sale.PosComponent');
	const Registries = require('point_of_sale.Registries');

	const BiProductsWidget = (ProductsWidget) =>
		class extends ProductsWidget {
			constructor() {
				super(...arguments);
			}

			get productsToDisplay() {
                var products_data = super.productsToDisplay;
                var seq_zero = []
                var seq_gr_zero = []

                _.each(products_data,function(pro){
                	if(pro.product_sequence == 0){
                		seq_zero.push(pro)
                	}else if(pro.product_sequence > 0){
                		seq_gr_zero.push(pro)
                	}
                })
                seq_gr_zero = seq_gr_zero.sort(function(a, b){
                	return a.product_sequence - b.product_sequence
                })
                seq_gr_zero = seq_gr_zero.concat(seq_zero);
                return seq_gr_zero
            }
		};

	Registries.Component.extend(ProductsWidget, BiProductsWidget);
	return ProductsWidget;
});
