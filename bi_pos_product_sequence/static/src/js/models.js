odoo.define('bi_pos_product_sequence.pos', function(require) {
	"use strict";

	var models = require('point_of_sale.models');
	var model_list = models.PosModel.prototype.models;

	models.load_fields('product.product', ['product_sequence']);
});