from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    silicie_asiento_ids = fields.One2many(
        'silicie.asiento', 'picking_id', string='Asientos SILICIE',
    )
    silicie_asiento_count = fields.Integer(
        string='Asientos SILICIE',
        compute='_compute_silicie_count',
    )

    @api.depends('silicie_asiento_ids')
    def _compute_silicie_count(self):
        for rec in self:
            rec.silicie_asiento_count = len(rec.silicie_asiento_ids)

    def _get_silicie_tipo_movimiento(self):
        """Devuelve el tipo de movimiento SILICIE según el tipo de operación del albarán."""
        code = self.picking_type_id.code
        if code == 'incoming':
            return 'A02'   # Entrada interior
        elif code == 'outgoing':
            return 'A08'   # Salida interior
        return False

    def _generar_asiento_silicie(self):
        """Genera asientos SILICIE a partir de un albarán validado (Nivel 2)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if not company.silicie_activo or not company.silicie_cae:
            return

        tipo = self._get_silicie_tipo_movimiento()
        if not tipo:
            return

        for move_line in self.move_line_ids.filtered(lambda ml: ml.qty_done > 0):
            lot = move_line.lot_id

            # Intentar obtener el grado alcohólico desde los parámetros del lote
            grado = 0.0
            if lot:
                param_alcohol = lot.parametro_quimico_ids.filtered(
                    lambda p: p.tipo_id and 'alcohol' in (p.tipo_id.name or '').lower()
                )
                if param_alcohol:
                    grado = param_alcohol[0].valor

            self.env['silicie.asiento'].create({
                'company_id': company.id,
                'nif': company.vat or '',
                'cae': company.silicie_cae,
                'fecha': self.date_done.date() if self.date_done else fields.Date.today(),
                'tipo_movimiento': tipo,
                'producto_codigo': '',   # El usuario debe rellenar el código SILICIE del producto
                'cantidad_litros': move_line.qty_done,
                'grado_alcoholico': grado,
                'justificante_tipo': 'alb',
                'justificante_numero': self.name,
                'origen_destino_nombre': self.partner_id.name if self.partner_id else '',
                'origen_destino_nif': self.partner_id.vat if self.partner_id else '',
                'lot_id': lot.id if lot else False,
                'picking_id': self.id,
                'estado': 'borrador',
            })

    def write(self, vals):
        res = super().write(vals)
        if vals.get('state') == 'done':
            # Solo generar si no existen ya asientos para este albarán
            for picking in self.filtered(lambda p: not p.silicie_asiento_ids):
                picking._generar_asiento_silicie()
        return res

    def action_ver_silicie(self):
        return {
            'name': 'Asientos SILICIE',
            'type': 'ir.actions.act_window',
            'res_model': 'silicie.asiento',
            'view_mode': 'list,form',
            'domain': [('picking_id', '=', self.id)],
            'context': {'default_picking_id': self.id},
        }
