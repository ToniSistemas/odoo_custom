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
    producto_codigo = fields.Char(
        string='Código producto SILICIE',
        required=True,
        help='Código según catálogo SILICIE de la AEAT.\n'
             'Ejemplos para vino (verificar en sede.agenciatributaria.gob.es):\n'
             ' - Vino tranquilo ≤15% vol\n'
             ' - Vino espumoso\n'
             ' - Mosto de uva',
    )
    cantidad_litros = fields.Float(
        string='Cantidad (litros)', digits=(14, 2), required=True,
    )
    grado_alcoholico = fields.Float(
        string='Grado alcohólico (% vol)', digits=(5, 2),
        help='Grado alcohólico volumétrico adquirido.',
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
    )

    # ── Observaciones ─────────────────────────────────────────────────────────
    observaciones = fields.Text(string='Observaciones')

    # ── Vínculos con Odoo ─────────────────────────────────────────────────────
    lot_id = fields.Many2one('stock.lot', string='Lote/Partida (Bodega)')
    picking_id = fields.Many2one('stock.picking', string='Albarán origen')

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
