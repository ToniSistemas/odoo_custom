from odoo import _, models
from odoo.exceptions import UserError

# (modelo, campo) donde un código escaneado ya tiene significado para Odoo
_BARCODE_OWNERS = [
    ('product.product', 'barcode'),
    ('product.uom', 'barcode'),
    ('stock.location', 'barcode'),
    ('stock.picking.type', 'barcode'),
    ('stock.lot', 'name'),
    ('stock.package', 'name'),
    ('stock.quant.package', 'name'),
]


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # ------------------------------------------------------------------
    # Búsqueda restringida al albarán
    # ------------------------------------------------------------------
    def _fashion_pending_moves(self):
        """Movimientos del albarán con variante sin EAN y cantidad pendiente."""
        self.ensure_one()
        if self.picking_type_code != 'incoming' or self.state in ('draft', 'done', 'cancel'):
            return self.env['stock.move']
        return self.move_ids.filtered(
            lambda m: m.state not in ('draft', 'done', 'cancel')
            and not m.product_id.barcode
            and m._fashion_qty_picked() < m.product_uom_qty
        )

    def _fashion_candidates(self):
        """Variantes candidatas agrupadas por producto (un producto puede tener varios moves)."""
        self.ensure_one()
        data = {}
        for move in self._fashion_pending_moves():
            vals = data.setdefault(move.product_id, {
                'id': move.product_id.id,
                'display_name': move.product_id.display_name,
                'default_code': move.product_id.default_code or '',
                'uom': move.product_uom.name,
                'qty_demand': 0.0,
                'qty_done': 0.0,
            })
            vals['qty_demand'] += move.product_uom_qty
            vals['qty_done'] += move._fashion_qty_picked()
        return list(data.values())

    def _fashion_barcode_in_use(self, barcode):
        # sudo: la unicidad del código es global, no depende de reglas de compañía
        for model_name, field_name in _BARCODE_OWNERS:
            if model_name not in self.env:
                continue
            Model = self.env[model_name].sudo().with_context(active_test=False)
            if Model.search_count([(field_name, '=', barcode)], limit=1):
                return True
        return False

    # ------------------------------------------------------------------
    # API pública (RPC desde wizard / app Barcode)
    # ------------------------------------------------------------------
    def fashion_get_barcode_candidates(self, barcode):
        """Devuelve si el código es desconocido y las variantes pendientes SOLO de este albarán."""
        self.ensure_one()
        barcode = (barcode or '').strip()
        if not barcode or self._fashion_barcode_in_use(barcode):
            return {'unknown': False, 'candidates': []}
        return {'unknown': True, 'candidates': self._fashion_candidates()}

    def fashion_assign_barcode_and_receive(self, barcode, product_id, receive=True):
        """Valida que product_id está pendiente en este albarán, le asigna el EAN y recibe 1 ud."""
        self.ensure_one()
        self.check_access('write')
        barcode = (barcode or '').strip()
        if not barcode:
            raise UserError(_("Debe escanear un código de barras."))
        if self.picking_type_code != 'incoming' or self.state in ('draft', 'done', 'cancel'):
            raise UserError(_("Solo se pueden asignar EAN en recepciones en curso."))

        product = self.env['product.product'].browse(int(product_id)).exists()
        moves = self._fashion_pending_moves().filtered(lambda m: m.product_id == product)
        if not moves:
            raise UserError(_(
                "La variante seleccionada no está pendiente de recibir en %(picking)s "
                "o ya tiene código de barras.", picking=self.display_name))
        if self._fashion_barcode_in_use(barcode):
            raise UserError(_("El código %(barcode)s ya está en uso en el sistema.", barcode=barcode))

        # sudo: el operario de almacén no tiene permiso de escritura en productos;
        # la operación queda acotada a variantes pendientes de este albarán y sin EAN previo.
        product.sudo().barcode = barcode
        self.message_post(body=_(
            "EAN %(barcode)s asignado a %(product)s durante la recepción.",
            barcode=barcode, product=product.display_name))

        result = {'received': False, 'message': _("EAN %s asignado.", barcode)}
        if receive:
            if product.tracking != 'none':
                result['message'] = _(
                    "EAN %s asignado. La variante se gestiona por lote/serie: "
                    "registre la cantidad indicando el lote.", barcode)
            else:
                self._fashion_receive_one(moves[0])
                result.update(received=True, message=_(
                    "EAN %(barcode)s asignado a %(product)s y +1 recibido.",
                    barcode=barcode, product=product.display_name))
        return result

    def fashion_receive_known_barcode(self, barcode):
        """+1 para un EAN ya existente cuya variante está en este albarán (flujo Community)."""
        self.ensure_one()
        self.check_access('write')
        product = self.env['product.product'].search([('barcode', '=', (barcode or '').strip())], limit=1)
        move = self.move_ids.filtered(
            lambda m: m.product_id == product and m.state not in ('draft', 'done', 'cancel'))[:1]
        if not move:
            raise UserError(_("El código %(barcode)s no corresponde a ninguna línea pendiente de %(picking)s.",
                              barcode=barcode, picking=self.display_name))
        if product.tracking != 'none':
            raise UserError(_("La variante %s requiere lote/serie: regístrela desde el detalle de la línea.",
                              product.display_name))
        self._fashion_receive_one(move)
        return {'received': True, 'message': _("+1 %s", product.display_name)}

    def _fashion_receive_one(self, move):
        lines = move.move_line_ids
        picked = lines.filtered('picked')
        if picked:
            picked[0].quantity += 1
        elif lines:
            # En recepciones la cantidad viene pre-reservada: la primera unidad escaneada la sustituye
            lines[0].write({'quantity': 1, 'picked': True})
        else:
            self.env['stock.move.line'].create({
                **move._prepare_move_line_vals(quantity=1),
                'picked': True,
            })

    def action_fashion_open_assign_wizard(self):
        self.ensure_one()
        return self.env['fashion.barcode.assign.wizard']._fashion_action(self)
