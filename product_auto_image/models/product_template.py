import base64
import logging
import re

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .image_search import (
    AutoImageFinder,
    FinderSettings,
    HttpClient,
    ProductSearchData,
    SearchProviderError,
    get_provider,
)

_logger = logging.getLogger(__name__)

PARAM_PREFIX = 'product_auto_image.'
SETTINGS_DEFAULTS = {
    'enabled': False,
    'min_score': 60,
    'timeout': 10,
    'max_image_kb': 5120,
    'replace_existing': False,
    'simulation': False,
    'max_results': 5,
    'request_interval': 2.0,
    'max_products': 20,
    'provider': 'duckduckgo',
    'searxng_url': '',
    'user_agent': '',
}

AUTO_IMAGE_METHODS = [
    ('manufacturer_reference', 'Referencia fabricante'),
    ('ean', 'EAN/GTIN'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Odoo 19 Community no dispone de campos de fabricante/marca en product.template.
    manufacturer_reference = fields.Char(
        'Referencia fabricante', index='btree_not_null',
        help='Referencia del fabricante que identifica el modelo/color (común a todas las tallas).')
    manufacturer_brand = fields.Char('Marca', index='btree_not_null')
    auto_image_url = fields.Char('URL imagen encontrada', readonly=True, copy=False)
    auto_image_preview_url = fields.Char(related='auto_image_url', string='Vista previa')
    auto_image_source = fields.Char('Página de origen', readonly=True, copy=False)
    auto_image_method = fields.Selection(AUTO_IMAGE_METHODS, 'Método utilizado', readonly=True, copy=False)
    auto_image_last_search = fields.Datetime('Última búsqueda', readonly=True, copy=False)
    auto_image_status = fields.Selection([
        ('pending', 'Pendiente'),
        ('found', 'Encontrada'),
        ('not_found', 'No encontrada'),
        ('error', 'Error'),
        ('manual', 'Manual'),
    ], 'Estado imagen automática', default='pending', copy=False, index=True)
    auto_image_error = fields.Text('Detalle / error', readonly=True, copy=False)
    auto_image_confidence = fields.Integer('Confianza', readonly=True, copy=False)
    auto_image_queued = fields.Boolean('En cola de búsqueda', copy=False, index=True)
    auto_image_log_count = fields.Integer(
        'Búsquedas de imagen', compute='_compute_auto_image_log_count', groups='base.group_user')

    def _compute_auto_image_log_count(self):
        counts = dict(self.env['product.auto.image.log']._read_group(
            [('product_id', 'in', self.ids)], ['product_id'], ['__count']))
        for product in self:
            product.auto_image_log_count = counts.get(product, 0)

    def write(self, vals):
        if vals.get('image_1920') and not self.env.context.get('auto_image_writing'):
            vals = dict(vals, auto_image_status='manual')
        return super().write(vals)

    # ------------------------------------------------------------------
    # Configuración
    # ------------------------------------------------------------------

    @api.model
    def _auto_image_get_settings(self):
        icp = self.env['ir.config_parameter'].sudo()
        settings = {}
        for key, default in SETTINGS_DEFAULTS.items():
            raw = icp.get_param(PARAM_PREFIX + key)
            if isinstance(default, bool):
                settings[key] = str(raw).strip().lower() in ('1', 'true', 'yes') if raw else False
            elif isinstance(default, (int, float)):
                try:
                    settings[key] = type(default)(float(raw)) if raw not in (None, False, '') else default
                except (TypeError, ValueError):
                    settings[key] = default
            else:
                settings[key] = raw or default
        settings['timeout'] = min(max(settings['timeout'], 1), 120)
        settings['request_interval'] = max(settings['request_interval'], 0.0)
        settings['max_results'] = min(max(settings['max_results'], 1), 20)
        settings['max_products'] = max(settings['max_products'], 1)
        settings['max_image_kb'] = max(settings['max_image_kb'], 50)
        return settings

    @api.model
    def _auto_image_build_finder(self, settings):
        http = HttpClient(
            timeout=settings['timeout'],
            min_interval=settings['request_interval'],
            user_agent=settings['user_agent'] or None,
        )
        try:
            provider = get_provider(settings['provider'], http, searxng_url=settings['searxng_url'], region='es-es')
        except SearchProviderError as exc:
            raise UserError(str(exc)) from exc
        return AutoImageFinder(provider, http, FinderSettings(
            min_score=settings['min_score'],
            max_results=settings['max_results'],
            max_image_bytes=settings['max_image_kb'] * 1024,
        ))

    def _auto_image_check_access(self):
        if not self.env.user._is_internal():
            raise AccessError(self.env._('Solo los usuarios internos pueden buscar imágenes automáticamente.'))
        self.check_access('write')

    # ------------------------------------------------------------------
    # Proceso
    # ------------------------------------------------------------------

    def _auto_image_search_data(self):
        """Datos de búsqueda a nivel de plantilla: una sola búsqueda por modelo,
        con los EAN de todas sus variantes como alternativa."""
        self.ensure_one()
        eans = []
        for barcode in self.product_variant_ids.mapped('barcode'):
            digits = re.sub(r'\D', '', barcode or '')
            if 8 <= len(digits) <= 14 and digits not in eans:
                eans.append(digits)
        return ProductSearchData(
            reference=(self.manufacturer_reference or '').strip(),
            brand=(self.manufacturer_brand or '').strip(),
            eans=eans,
            name=self.name or '',
        )

    def _auto_image_process(self, replace_existing=None, simulation=None, finder=None):
        """Procesa los productos de uno en uno. Un error en un producto no detiene el resto.

        :return: registros product.auto.image.log creados
        """
        settings = self._auto_image_get_settings()
        replace = settings['replace_existing'] if replace_existing is None else replace_existing
        simulate = settings['simulation'] if simulation is None else simulation
        finder = finder or self._auto_image_build_finder(settings)
        logs = self.env['product.auto.image.log']
        for product in self:
            try:
                with self.env.cr.savepoint():
                    logs |= product._auto_image_process_one(finder, replace, simulate)
            except Exception as exc:  # aislar cualquier fallo inesperado por producto
                _logger.exception('Error buscando imagen para el producto %s', product.id)
                logs |= product._auto_image_register_error(exc)
        return logs

    def _auto_image_log_vals(self, data):
        return {
            'product_id': self.id,
            'manufacturer_reference': data.reference,
            'manufacturer_brand': data.brand,
            'ean': ', '.join(data.eans),
        }

    def _auto_image_process_one(self, finder, replace, simulate):
        self.ensure_one()
        Log = self.env['product.auto.image.log'].sudo()
        data = self._auto_image_search_data()
        log_vals = self._auto_image_log_vals(data)

        if self.image_1920 and not replace and not simulate:
            return Log.create(dict(
                log_vals, status='skipped',
                error_message=self.env._('El producto ya tiene imagen y no se ha solicitado reemplazarla.')))

        result = finder.find(data)
        candidate = result.candidate
        product_vals = {
            'auto_image_last_search': fields.Datetime.now(),
            'auto_image_method': result.method or False,
            'auto_image_confidence': candidate.confidence if candidate else 0,
        }
        log_vals.update({
            'search_query': result.search_query,
            'search_method': result.method or False,
            'source_url': candidate.page_url if candidate else False,
            'image_url': candidate.image_url if candidate else False,
            'confidence': candidate.confidence if candidate else 0,
            'notes': '\n'.join(result.notes),
        })

        if result.status == 'found':
            product_vals.update({
                'auto_image_url': candidate.image_url,
                'auto_image_source': candidate.page_url,
            })
            if simulate:
                product_vals['auto_image_error'] = self.env._('Simulación: la imagen no se ha guardado.')
                log_vals['status'] = 'simulated'
            else:
                product_vals.update({
                    'image_1920': base64.b64encode(candidate.image.data),
                    'auto_image_status': 'found',
                    'auto_image_error': False,
                })
                log_vals['status'] = 'found'
        else:
            product_vals.update({
                'auto_image_error': result.error,
                'auto_image_url': False,
                'auto_image_source': False,
            })
            if not simulate:
                product_vals['auto_image_status'] = result.status
            log_vals.update({'status': result.status, 'error_message': result.error})

        self.with_context(auto_image_writing=True).write(product_vals)
        return Log.create(log_vals)

    def _auto_image_register_error(self, exc):
        self.ensure_one()
        message = str(exc) or exc.__class__.__name__
        try:
            with self.env.cr.savepoint():
                self.with_context(auto_image_writing=True).write({
                    'auto_image_status': 'error',
                    'auto_image_error': message,
                    'auto_image_last_search': fields.Datetime.now(),
                })
        except Exception:
            _logger.exception('No se pudo marcar el error en el producto %s', self.id)
        return self.env['product.auto.image.log'].sudo().create({
            'product_id': self.id,
            'manufacturer_reference': self.manufacturer_reference,
            'manufacturer_brand': self.manufacturer_brand,
            'status': 'error',
            'error_message': message,
        })

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def action_auto_image_search(self):
        self._auto_image_check_access()
        settings = self._auto_image_get_settings()
        if len(self) > settings['max_products']:
            raise UserError(self.env._(
                'Máximo %(max)s productos por ejecución. Use el asistente en segundo plano.',
                max=settings['max_products']))
        logs = self._auto_image_process()
        if len(logs) == 1:
            messages = {
                'found': (self.env._('Imagen encontrada y guardada (confianza %s).', logs.confidence), 'success'),
                'simulated': (self.env._('Simulación: imagen encontrada (confianza %s), no guardada.', logs.confidence), 'info'),
                'not_found': (self.env._('No se encontró ninguna imagen fiable.'), 'warning'),
                'error': (logs.error_message or self.env._('Error en la búsqueda.'), 'danger'),
                'skipped': (logs.error_message, 'warning'),
            }
            message, kind = messages[logs.status]
        else:
            found = len(logs.filtered(lambda log: log.status in ('found', 'simulated')))
            message, kind = self.env._('%(found)s de %(total)s productos con imagen.', found=found, total=len(logs)), 'info'
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Búsqueda automática de imagen'),
                'message': message,
                'type': kind,
                'sticky': kind == 'danger',
                'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'},
            },
        }

    def action_view_auto_image_logs(self):
        action = self.env['ir.actions.act_window']._for_xml_id('product_auto_image.action_product_auto_image_log')
        action['domain'] = [('product_id', 'in', self.ids)]
        action['context'] = {}
        return action

    @api.model
    def _cron_auto_image_search(self):
        settings = self._auto_image_get_settings()
        limit = settings['max_products']
        products = self.search([('auto_image_queued', '=', True)], limit=limit)
        if settings['enabled'] and len(products) < limit:
            products |= self.search([
                ('auto_image_queued', '=', False),
                ('auto_image_status', '=', 'pending'),
                ('image_1920', '=', False),
                '|', ('manufacturer_reference', '!=', False), ('product_variant_ids.barcode', '!=', False),
            ], limit=limit - len(products))
        if not products:
            return
        finder = self._auto_image_build_finder(settings)
        IrCron = self.env['ir.cron']
        for index, product in enumerate(products, start=1):
            product._auto_image_process(finder=finder)
            product.auto_image_queued = False
            if IrCron._commit_progress(1, remaining=len(products) - index) <= 0:
                break
