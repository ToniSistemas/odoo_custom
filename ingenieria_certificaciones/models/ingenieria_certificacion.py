from odoo import models, fields, api, _
from odoo.exceptions import UserError


class IngenieriaCertificacion(models.Model):
    _name = 'ingenieria.certificacion'
    _description = 'Certificación de Obra'
    _order = 'date desc, name desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número',
        readonly=True,
        copy=False,
        default='Nuevo',
    )
    project_id = fields.Many2one(
        'project.project',
        string='Proyecto',
        required=True,
        tracking=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pedido / Contrato',
        required=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        related='sale_order_id.partner_id',
        store=True,
        readonly=True,
    )
    date = fields.Date(
        string='Fecha de certificación',
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    date_from = fields.Date(string='Período desde')
    date_to = fields.Date(string='Período hasta')
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('invoiced', 'Facturada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True, copy=False)
    line_ids = fields.One2many(
        'ingenieria.certificacion.line',
        'certificacion_id',
        string='Partidas',
    )
    amount_total = fields.Monetary(
        string='Total certificación',
        compute='_compute_amount_total',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='sale_order_id.currency_id',
        store=True,
    )
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        readonly=True,
        copy=False,
    )
    notes = fields.Text(string='Notas / Observaciones')

    @api.depends('line_ids.amount')
    def _compute_amount_total(self):
        for rec in self:
            rec.amount_total = sum(rec.line_ids.mapped('amount'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('ingenieria.certificacion')
                    or 'Nuevo'
                )
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_(
                    'La certificación no tiene partidas. '
                    'Añada al menos una partida antes de confirmar.'
                ))
            rec.state = 'confirmed'

    def action_create_invoice(self):
        self.ensure_one()
        if self.state != 'confirmed':
            raise UserError(_('Solo se pueden facturar certificaciones confirmadas.'))
        if self.invoice_id:
            raise UserError(_('Esta certificación ya tiene una factura asociada.'))
        if not self.line_ids:
            raise UserError(_('La certificación no tiene partidas.'))

        invoice_line_vals = []
        for line in self.line_ids:
            vals = {
                'name': line.name,
                'quantity': line.qty_periodo,
                'price_unit': line.price_unit,
            }
            if line.product_id:
                vals['product_id'] = line.product_id.id
            if line.uom_id:
                vals['product_uom_id'] = line.uom_id.id
            # Enlazar con la línea del pedido para que Odoo cuente
            # esta factura en el botón inteligente del pedido de venta
            if line.sale_line_id:
                vals['sale_line_ids'] = [(4, line.sale_line_id.id)]
            invoice_line_vals.append((0, 0, vals))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.date,
            'invoice_origin': self.sale_order_id.name,
            'invoice_line_ids': invoice_line_vals,
            'narration': 'Certificación %s — Proyecto: %s' % (
                self.name, self.project_id.name
            ),
        })
        self.write({'invoice_id': invoice.id, 'state': 'invoiced'})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(_(
                    'No se puede cancelar una certificación ya facturada. '
                    'Cancele primero la factura.'
                ))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            if rec.state == 'cancelled':
                rec.state = 'draft'

    def action_print_certificacion(self):
        return self.env.ref(
            'ingenieria_certificaciones.action_report_certificacion'
        ).report_action(self)
