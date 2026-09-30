from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FashionBarcodeAssignWizard(models.TransientModel):
    _name = 'fashion.barcode.assign.wizard'
    _description = 'Asignación rápida de EAN en recepción'

    picking_id = fields.Many2one('stock.picking', required=True, readonly=True, ondelete='cascade')
    barcode = fields.Char(string="EAN escaneado")
    line_ids = fields.One2many('fashion.barcode.assign.wizard.line', 'wizard_id', string="Variantes pendientes")
    allowed_product_ids = fields.Many2many('product.product', compute='_compute_allowed_product_ids')
    product_id = fields.Many2one(
        'product.product', string="Variante",
        domain="[('id', 'in', allowed_product_ids)]")
    known_product_id = fields.Many2one('product.product', compute='_compute_known_product_id')
    last_message = fields.Char(readonly=True)

    @api.model
    def _fashion_action(self, picking, product=None, message=False):
        ctx = {'default_picking_id': picking.id, 'default_last_message': message}
        if product:
            ctx['default_product_id'] = product.id
        return {
            'type': 'ir.actions.act_window',
            'name': _("Asignar EAN - %s", picking.display_name),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking = self.env['stock.picking'].browse(res.get('picking_id'))
        if picking:
            if picking.picking_type_code != 'incoming':
                raise UserError(_("La asignación de EAN solo está disponible en recepciones."))
            candidates = picking._fashion_candidates()
            res['line_ids'] = [fields.Command.create({
                'product_id': c['id'],
                'qty_demand': c['qty_demand'],
                'qty_done': c['qty_done'],
            }) for c in candidates]
            if not res.get('product_id') and len(candidates) == 1:
                res['product_id'] = candidates[0]['id']
        return res

    @api.depends('line_ids.product_id')
    def _compute_allowed_product_ids(self):
        for wizard in self:
            wizard.allowed_product_ids = wizard.line_ids.product_id

    @api.depends('barcode')
    def _compute_known_product_id(self):
        Product = self.env['product.product']
        for wizard in self:
            code = (wizard.barcode or '').strip()
            wizard.known_product_id = Product.search([('barcode', '=', code)], limit=1) if code else False

    def _fashion_process(self, product):
        self.ensure_one()
        picking = self.picking_id
        if self.known_product_id:
            result = picking.fashion_receive_known_barcode(self.barcode)
        else:
            if not product:
                raise UserError(_("Seleccione la variante a la que corresponde el código escaneado."))
            result = picking.fashion_assign_barcode_and_receive(self.barcode, product.id)
        if picking._fashion_pending_moves() or self.known_product_id:
            return self._fashion_action(picking, message=result['message'])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'success',
                'message': result['message'],
                'next': {'type': 'ir.actions.act_window_close'},
            },
        }

    def action_assign_and_receive(self):
        return self._fashion_process(self.product_id)

    def action_assign_all_and_receive(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda line: (line.barcode or '').strip())
        if not lines:
            raise UserError(_("Escriba al menos un EAN en las líneas antes de asignar."))

        barcodes = [line.barcode.strip() for line in lines]
        if len(barcodes) != len(set(barcodes)):
            raise UserError(_("No puede repetir el mismo EAN en varias líneas."))

        for line, barcode in zip(lines, barcodes):
            if self.picking_id._fashion_barcode_in_use(barcode):
                raise UserError(_(
                    "El código %(barcode)s de %(product)s ya está en uso en el sistema.",
                    barcode=barcode, product=line.product_id.display_name))
            if not self.picking_id._fashion_pending_moves().filtered(
                    lambda move: move.product_id == line.product_id and not move.product_id.barcode):
                raise UserError(_(
                    "La variante %(product)s ya no está pendiente en este albarán.",
                    product=line.product_id.display_name))

        messages = []
        for line, barcode in zip(lines, barcodes):
            result = self.picking_id.fashion_assign_barcode_and_receive(
                barcode, line.product_id.id)
            messages.append(result['message'])
        return self._fashion_action(self.picking_id, message=_(
            "Se han asignado %s EAN y recibido la demanda completa de cada variante.",
            len(messages)))


class FashionBarcodeAssignWizardLine(models.TransientModel):
    _name = 'fashion.barcode.assign.wizard.line'
    _description = 'Variante pendiente en asignación de EAN'

    wizard_id = fields.Many2one('fashion.barcode.assign.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string="Variante", required=True, readonly=True)
    default_code = fields.Char(related='product_id.default_code')
    barcode = fields.Char(string="EAN")
    qty_demand = fields.Float(string="Pedido", digits='Product Unit', readonly=True)
    qty_done = fields.Float(string="Recibido", digits='Product Unit', readonly=True)

    def action_assign_and_receive(self):
        self.ensure_one()
        barcode = (self.barcode or '').strip()
        if not barcode:
            raise UserError(_("Escriba el EAN en la línea de %s.", self.product_id.display_name))
        result = self.wizard_id.picking_id.fashion_assign_barcode_and_receive(
            barcode, self.product_id.id)
        return self.wizard_id._fashion_action(
            self.wizard_id.picking_id, message=result['message'])
