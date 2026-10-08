from odoo import api, fields, models

from .product_template import AUTO_IMAGE_METHODS


class ProductAutoImageLog(models.Model):
    _name = 'product.auto.image.log'
    _description = 'Registro de búsqueda automática de imágenes'
    _order = 'create_date desc, id desc'

    product_id = fields.Many2one(
        'product.template', string='Producto', ondelete='cascade', index=True, readonly=True)
    manufacturer_reference = fields.Char('Referencia fabricante', readonly=True)
    manufacturer_brand = fields.Char('Marca', readonly=True)
    ean = fields.Char('EAN', readonly=True)
    search_query = fields.Text('Consultas realizadas', readonly=True)
    search_method = fields.Selection(AUTO_IMAGE_METHODS, string='Método', readonly=True)
    source_url = fields.Char('Página de origen', readonly=True)
    image_url = fields.Char('URL de la imagen', readonly=True)
    confidence = fields.Integer('Confianza', readonly=True)
    status = fields.Selection([
        ('found', 'Imagen guardada'),
        ('simulated', 'Encontrada (simulación)'),
        ('not_found', 'No encontrada'),
        ('error', 'Error'),
        ('skipped', 'Omitido (ya tenía imagen)'),
    ], string='Estado', readonly=True, index=True)
    error_message = fields.Text('Mensaje', readonly=True)
    notes = fields.Text('Detalle de la búsqueda', readonly=True)

    @api.depends('product_id', 'status')
    def _compute_display_name(self):
        status_labels = dict(self._fields['status']._description_selection(self.env))
        for log in self:
            log.display_name = f'{log.product_id.display_name or "-"} · {status_labels.get(log.status, "")}'
