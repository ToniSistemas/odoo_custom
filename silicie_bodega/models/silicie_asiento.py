from odoo import models, fields, api

TIPOS_MOVIMIENTO = [
    ('A01', 'A01 - Apertura'),
    ('A02', 'A02 - Entrada interior (+)'),
    ('A04', 'A04 - Entrada UE (+)'),
    ('A06', 'A06 - Entrada importación (+)'),
    ('A07', 'A07 - Entrada devolución art.55 RIE (+)'),
    ('A08', 'A08 - Salida interior (-)'),
    ('A10', 'A10 - Salida UE (-)'),
    ('A11', 'A11 - Salida exportación (-)'),
    ('A14', 'A14 - Autoconsumo/empleado (-)'),
    ('A15', 'A15 - Fabricado/obtenido (+)'),
    ('A16', 'A16 - Entrada por cambio de código (+)'),
    ('A17', 'A17 - Salida por cambio de código (-)'),
    ('A21', 'A21 - Salida almacén auxiliar'),
    ('A22', 'A22 - Entrada almacén auxiliar'),
    ('A28', 'A28 - Destrucción (-)'),
    ('A30', 'A30 - Diferencias en menos almacenamiento (-)'),
    ('A31', 'A31 - Diferencias en más almacenamiento (+)'),
    ('A32', 'A32 - Diferencias en menos fabricación'),
    ('A33', 'A33 - Diferencias en más fabricación'),
    ('A35', 'A35 - Ajustes positivos de mediciones (+)'),
    ('A36', 'A36 - Ajustes negativos de mediciones (-)'),
    ('A40', 'A40 - Utilización fines exentos (-)'),
    ('A41', 'A41 - Autoconsumo operaciones propias (-)'),
    ('A42', 'A42 - Ajustes positivos ejercicios anteriores (+)'),
    ('A43', 'A43 - Ajustes negativos ejercicios anteriores (-)'),
]

TIPOS_JUSTIFICANTE = [
    ('alb', 'Albarán'),
    ('fra', 'Factura'),
    ('ead', 'e-AD (Documento Aduanero Electrónico)'),
    ('dua', 'DUA'),
    ('otros', 'Otros'),
]


class SilicieAsiento(models.Model):
    _name = 'silicie.asiento'
    _description = 'Asiento contable SILICIE'
    _order = 'fecha desc, id desc'

    name = fields.Char(string='Referencia', readonly=True, default='/')
    estado = fields.Selection([
        ('borrador', 'Borrador'),
        ('confirmado', 'Confirmado'),
        ('exportado', 'Exportado'),
    ], string='Estado', default='borrador', required=True)

    # ── Datos del operador ────────────────────────────────────────────────────
    company_id = fields.Many2one(
        'res.company', string='Empresa', required=True,
        default=lambda self: self.env.company,
    )
    nif = fields.Char(
        string='NIF titular',
        required=True,
        default=lambda self: self.env.company.vat or '',
    )
    cae = fields.Char(
        string='CAE',
        required=True,
        default=lambda self: self.env.company.silicie_cae or '',
        help='Código de Actividad y Establecimiento asignado por la AEAT.',
    )

    # ── Datos del asiento ─────────────────────────────────────────────────────
    fecha = fields.Date(string='Fecha movimiento', required=True, default=fields.Date.today)
    tipo_movimiento = fields.Selection(TIPOS_MOVIMIENTO, string='Tipo de movimiento', required=True)

    # ── Producto ──────────────────────────────────────────────────────────────
    product_id = fields.Many2one(
        'product.product', string='Producto',
        help='El lote aporta los datos efectivos; el producto se usa como valor predeterminado.',
    )
    producto_codigo = fields.Char(
        string='Código NC', readonly=True,
    )
    epigrafe_fiscal = fields.Char(
        string='Epígrafe fiscal AEAT', readonly=True,
    )
    cantidad_litros = fields.Float(
        string='Cantidad (litros)', digits=(14, 2), required=True,
    )
    grado_alcoholico = fields.Float(
        string='Grado alcohólico (% vol)', digits=(5, 2),
        readonly=True,
    )
    litros_alcohol_puro = fields.Float(
        string='Litros de alcohol puro (LAP)',
        digits=(14, 4),
        compute='_compute_lap',
        store=True,
        help='Calculado automáticamente: cantidad × grado / 100',
    )

    # ── Justificante ──────────────────────────────────────────────────────────
    justificante_tipo = fields.Selection(TIPOS_JUSTIFICANTE, string='Tipo justificante')
    justificante_numero = fields.Char(string='Nº justificante')

    # ── Origen / Destino ──────────────────────────────────────────────────────
    origen_destino_nif = fields.Char(string='NIF origen/destino')
    origen_destino_cae = fields.Char(string='CAE origen/destino')
    origen_destino_nombre = fields.Char(string='Nombre origen/destino')

    # ── Envases ───────────────────────────────────────────────────────────────
    num_envases = fields.Integer(string='Nº envases')
    capacidad_envase = fields.Float(
        string='Capacidad envase (litros)', digits=(5, 3),
        readonly=True,
    )

    # ── Observaciones ─────────────────────────────────────────────────────────
    observaciones = fields.Text(string='Observaciones')

    # ── Vínculos con Odoo ─────────────────────────────────────────────────────
    lot_id = fields.Many2one('stock.lot', string='Lote/Partida (Bodega)')
    picking_id = fields.Many2one('stock.picking', string='Albarán origen')

    @api.onchange('product_id', 'lot_id')
    def _onchange_product_lot(self):
        for record in self:
            product = record.product_id
            lot = record.lot_id
            if lot and lot.product_id:
                product = lot.product_id
                record.product_id = product
            if not product:
                continue
            code = lot.silicie_codigo_nc_id if lot else product.silicie_codigo_nc_id
            record.producto_codigo = code.codigo if code else False
            record.epigrafe_fiscal = code.epigrafe_fiscal if code else False
            record.grado_alcoholico = (
                lot.silicie_grado_alcoholico if lot and lot.silicie_grado_alcoholico
                else product.silicie_grado_alcoholico
            )
            record.capacidad_envase = (
                lot.silicie_capacidad_envase if lot and lot.silicie_capacidad_envase
                else product.silicie_capacidad_envase
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            product = self.env['product.product'].browse(vals['product_id']) if vals.get('product_id') else self.env['product.product']
            lot = self.env['stock.lot'].browse(vals['lot_id']) if vals.get('lot_id') else self.env['stock.lot']
            if lot and lot.product_id:
                product = lot.product_id
                vals.setdefault('product_id', product.id)
            code = lot.silicie_codigo_nc_id if lot else product.silicie_codigo_nc_id
            if code and not vals.get('producto_codigo'):
                vals['producto_codigo'] = code.codigo
            if code and not vals.get('epigrafe_fiscal'):
                vals['epigrafe_fiscal'] = code.epigrafe_fiscal
            if not vals.get('grado_alcoholico'):
                vals['grado_alcoholico'] = (
                    lot.silicie_grado_alcoholico if lot and lot.silicie_grado_alcoholico
                    else product.silicie_grado_alcoholico
                )
            if not vals.get('capacidad_envase'):
                vals['capacidad_envase'] = (
                    lot.silicie_capacidad_envase if lot and lot.silicie_capacidad_envase
                    else product.silicie_capacidad_envase
                )
        return super().create(vals_list)

    # ── Cómputos ──────────────────────────────────────────────────────────────
    @api.depends('cantidad_litros', 'grado_alcoholico')
    def _compute_lap(self):
        for rec in self:
            if rec.grado_alcoholico:
                rec.litros_alcohol_puro = rec.cantidad_litros * rec.grado_alcoholico / 100.0
            else:
                rec.litros_alcohol_puro = 0.0

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            self.nif = self.company_id.vat or ''
            self.cae = self.company_id.silicie_cae or ''

    # ── Secuencia ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('silicie.asiento') or '/'
        return super().create(vals_list)

    # ── Acciones de estado ────────────────────────────────────────────────────
    def action_confirmar(self):
        self.write({'estado': 'confirmado'})

    def action_borrador(self):
        self.write({'estado': 'borrador'})
