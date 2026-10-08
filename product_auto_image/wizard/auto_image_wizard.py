from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class ProductAutoImageWizard(models.TransientModel):
    _name = 'product.auto.image.wizard'
    _description = 'Asistente de búsqueda automática de imágenes'

    def _default_setting(self, key):
        return self.env['product.template']._auto_image_get_settings()[key]

    product_ids = fields.Many2many('product.template', string='Productos')
    product_count = fields.Integer('Nº de productos', compute='_compute_product_count')
    replace_existing = fields.Boolean(
        'Reemplazar imágenes existentes', default=lambda self: self._default_setting('replace_existing'))
    simulation = fields.Boolean(
        'Solo buscar, no descargar', default=lambda self: self._default_setting('simulation'))
    run_in_background = fields.Boolean(
        'Procesar en segundo plano',
        help='Encola los productos y los procesa la acción planificada, '
             'con la configuración general de Ajustes.')
    max_products = fields.Integer(
        'Máximo por ejecución', readonly=True, default=lambda self: self._default_setting('max_products'))
    state = fields.Selection([('draft', 'Borrador'), ('done', 'Terminado')], default='draft')
    summary = fields.Text('Resumen', readonly=True)
    log_ids = fields.Many2many('product.auto.image.log', string='Resultados', readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        context = self.env.context
        active_ids = context.get('active_ids') or []
        if 'product_ids' in fields_list and active_ids:
            if context.get('active_model') == 'product.template':
                templates = self.env['product.template'].browse(active_ids)
            elif context.get('active_model') == 'product.product':
                templates = self.env['product.product'].browse(active_ids).product_tmpl_id
            else:
                templates = self.env['product.template']
            res['product_ids'] = [Command.set(templates.ids)]
        return res

    @api.depends('product_ids')
    def _compute_product_count(self):
        for wizard in self:
            wizard.product_count = len(wizard.product_ids)

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_run(self):
        self.ensure_one()
        products = self.product_ids
        if not products:
            raise UserError(self.env._('Seleccione al menos un producto.'))
        products._auto_image_check_access()

        if self.run_in_background:
            products.write({'auto_image_queued': True})
            self.env.ref('product_auto_image.ir_cron_product_auto_image').sudo()._trigger()
            self.write({
                'state': 'done',
                'summary': self.env._(
                    '%(count)s productos añadidos a la cola. Se procesarán en segundo plano '
                    '(máximo %(max)s por ejecución).', count=len(products), max=self.max_products),
            })
            return self._reopen()

        if len(products) > self.max_products:
            raise UserError(self.env._(
                'Ha seleccionado %(count)s productos y el máximo por ejecución es %(max)s. '
                'Marque "Procesar en segundo plano" o reduzca la selección.',
                count=len(products), max=self.max_products))

        logs = products._auto_image_process(
            replace_existing=self.replace_existing, simulation=self.simulation)
        counts = {status: len(logs.filtered(lambda log, s=status: log.status == s))
                  for status in ('found', 'simulated', 'not_found', 'error', 'skipped')}
        summary = self.env._(
            'Procesados: %(total)s\n'
            'Imagen guardada: %(found)s\n'
            'Encontrada (simulación): %(simulated)s\n'
            'No encontrada: %(not_found)s\n'
            'Errores: %(error)s\n'
            'Omitidos (ya tenían imagen): %(skipped)s',
            total=len(logs), **counts)
        self.write({'state': 'done', 'summary': summary, 'log_ids': [Command.set(logs.ids)]})
        return self._reopen()

    def action_open_logs(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('product_auto_image.action_product_auto_image_log')
        action['domain'] = [('id', 'in', self.log_ids.ids)] if self.log_ids else [
            ('product_id', 'in', self.product_ids.ids)]
        action['context'] = {}
        return action
