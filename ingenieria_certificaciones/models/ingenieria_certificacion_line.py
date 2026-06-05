from odoo import models, fields, api


class IngenieriaCertificacionLine(models.Model):
    _name = 'ingenieria.certificacion.line'
    _description = 'Línea de Certificación de Obra'
    _order = 'sequence, id'

    certificacion_id = fields.Many2one(
        'ingenieria.certificacion',
        string='Certificación',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(string='Sec.', default=10)
    sale_line_id = fields.Many2one(
        'sale.order.line',
        string='Partida del contrato',
        domain="[('order_id', '=', parent.sale_order_id), ('order_id', '!=', False)]",
    )
    name = fields.Char(string='Descripción', required=True)
    product_id = fields.Many2one('product.product', string='Producto')
    uom_id = fields.Many2one('uom.uom', string='Unidad')

    # Cantidades del contrato y certificación
    qty_contrato = fields.Float(
        string='Qty. Contrato',
        digits='Product Unit of Measure',
        help='Cantidad total contratada para esta partida',
    )
    qty_certificado_ant = fields.Float(
        string='Cert. Anterior',
        compute='_compute_qty_certificado_ant',
        digits='Product Unit of Measure',
        help='Cantidad acumulada certificada en certificaciones anteriores confirmadas o facturadas',
    )
    qty_periodo = fields.Float(
        string='Este período',
        digits='Product Unit of Measure',
        required=True,
        default=0.0,
    )
    qty_certificado_total = fields.Float(
        string='Total certif.',
        compute='_compute_totales',
        digits='Product Unit of Measure',
    )
    qty_pendiente = fields.Float(
        string='Pendiente',
        compute='_compute_totales',
        digits='Product Unit of Measure',
    )
    progress_pct = fields.Float(
        string='% Avance',
        compute='_compute_totales',
        digits=(5, 1),
        help='Porcentaje del total contratado certificado acumulado (incluyendo este período)',
    )
    price_unit = fields.Float(
        string='Precio unit.',
        digits='Product Price',
    )
    amount = fields.Monetary(
        string='Importe',
        compute='_compute_amount',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='certificacion_id.currency_id',
        store=True,
    )

    @api.onchange('sale_line_id')
    def _onchange_sale_line_id(self):
        if self.sale_line_id:
            line = self.sale_line_id
            self.name = line.name
            self.product_id = line.product_id
            self.uom_id = line.product_uom_id
            self.qty_contrato = line.product_uom_qty
            self.price_unit = line.price_unit

    @api.depends('sale_line_id', 'certificacion_id')
    def _compute_qty_certificado_ant(self):
        for line in self:
            if not line.sale_line_id:
                line.qty_certificado_ant = 0.0
                continue
            # _origin.id es False para registros nuevos no guardados aún
            cert_db_id = line.certificacion_id._origin.id
            domain = [
                ('sale_line_id', '=', line.sale_line_id.id),
                ('certificacion_id.state', 'in', ['confirmed', 'invoiced']),
            ]
            if cert_db_id:
                domain.append(('certificacion_id', '!=', cert_db_id))
            prev_lines = self.search(domain)
            line.qty_certificado_ant = sum(prev_lines.mapped('qty_periodo'))

    @api.depends('qty_certificado_ant', 'qty_periodo', 'qty_contrato')
    def _compute_totales(self):
        for line in self:
            line.qty_certificado_total = line.qty_certificado_ant + line.qty_periodo
            line.qty_pendiente = line.qty_contrato - line.qty_certificado_total
            if line.qty_contrato:
                line.progress_pct = (line.qty_certificado_total / line.qty_contrato) * 100.0
            else:
                line.progress_pct = 0.0

    @api.depends('qty_periodo', 'price_unit')
    def _compute_amount(self):
        for line in self:
            line.amount = line.qty_periodo * line.price_unit
