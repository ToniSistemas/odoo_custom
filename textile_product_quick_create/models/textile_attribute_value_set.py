from odoo import api, fields, models
from odoo.exceptions import ValidationError


class TextileAttributeValueSet(models.Model):
    _name = 'textile.attribute.value.set'
    _description = 'Juego de valores de atributo'
    _order = 'attribute_id, sequence, id'

    name = fields.Char(string="Nombre", required=True, translate=True)
    sequence = fields.Integer(default=10)
    attribute_id = fields.Many2one(
        'product.attribute', string="Atributo", required=True, ondelete='cascade', index=True)
    value_ids = fields.Many2many(
        'product.attribute.value', string="Valores", required=True,
        domain="[('attribute_id', '=', attribute_id)]")

    @api.constrains('attribute_id', 'value_ids')
    def _check_values_attribute(self):
        for value_set in self:
            if value_set.value_ids.attribute_id - value_set.attribute_id:
                raise ValidationError(self.env._(
                    "Todos los valores del juego %s deben pertenecer al atributo %s.",
                    value_set.name, value_set.attribute_id.name))


class ProductAttribute(models.Model):
    _inherit = 'product.attribute'

    textile_value_set_ids = fields.One2many(
        'textile.attribute.value.set', 'attribute_id', string="Juegos de valores")
