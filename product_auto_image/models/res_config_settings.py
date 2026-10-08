from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .image_search import SEARCH_PROVIDERS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    @api.model
    def _auto_image_provider_selection(self):
        return [(code, provider.label) for code, provider in SEARCH_PROVIDERS.items()]

    auto_image_enabled = fields.Boolean(
        'Búsqueda automática programada', config_parameter='product_auto_image.enabled')
    auto_image_min_score = fields.Integer(
        'Puntuación mínima', config_parameter='product_auto_image.min_score', default=60)
    auto_image_timeout = fields.Integer(
        'Timeout HTTP (segundos)', config_parameter='product_auto_image.timeout', default=10)
    auto_image_max_image_kb = fields.Integer(
        'Tamaño máximo de imagen (KB)', config_parameter='product_auto_image.max_image_kb', default=5120)
    auto_image_replace_existing = fields.Boolean(
        'Reemplazar imágenes existentes', config_parameter='product_auto_image.replace_existing')
    auto_image_simulation = fields.Boolean(
        'Solo buscar, no descargar', config_parameter='product_auto_image.simulation')
    auto_image_max_results = fields.Integer(
        'Número máximo de resultados', config_parameter='product_auto_image.max_results', default=5)
    auto_image_request_interval = fields.Float(
        'Intervalo entre peticiones (segundos)', config_parameter='product_auto_image.request_interval',
        default=2.0)
    auto_image_max_products = fields.Integer(
        'Máximo de productos por ejecución', config_parameter='product_auto_image.max_products', default=20)
    auto_image_provider = fields.Selection(
        '_auto_image_provider_selection', string='Proveedor de búsqueda',
        config_parameter='product_auto_image.provider', default='duckduckgo')
    auto_image_searxng_url = fields.Char(
        'URL de SearXNG', config_parameter='product_auto_image.searxng_url')

    @api.constrains(
        'auto_image_min_score', 'auto_image_timeout', 'auto_image_max_image_kb', 'auto_image_max_results',
        'auto_image_request_interval', 'auto_image_max_products')
    def _check_auto_image_values(self):
        for record in self:
            if not 1 <= record.auto_image_timeout <= 120:
                raise ValidationError(self.env._('El timeout debe estar entre 1 y 120 segundos.'))
            if record.auto_image_request_interval < 1:
                raise ValidationError(self.env._('El intervalo entre peticiones debe ser de al menos 1 segundo.'))
            if not 1 <= record.auto_image_max_results <= 20:
                raise ValidationError(self.env._('El número máximo de resultados debe estar entre 1 y 20.'))
            if record.auto_image_max_products < 1:
                raise ValidationError(self.env._('El máximo de productos por ejecución debe ser al menos 1.'))
            if record.auto_image_max_image_kb < 50:
                raise ValidationError(self.env._('El tamaño máximo de imagen debe ser de al menos 50 KB.'))
            if not 0 <= record.auto_image_min_score <= 200:
                raise ValidationError(self.env._('La puntuación mínima debe estar entre 0 y 200.'))
