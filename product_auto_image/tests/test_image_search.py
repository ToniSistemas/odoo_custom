import base64

import requests

from odoo.exceptions import AccessError
from odoo.fields import Command
from odoo.tests import TransactionCase, tagged

from ..models.image_search import (
    AutoImageFinder,
    DuckDuckGoHtmlProvider,
    HttpClient,
    ProductSearchData,
    UnsafeUrlError,
)
from .common import FakeWeb, ddg_results_html, ddg_url, make_image, product_page_html

DDG = DuckDuckGoHtmlProvider.endpoint

EX1 = {'brand': 'REPLAY', 'ref': 'DK4220.000.G23726', 'eans': ['8053816464315']}
EX2 = {'brand': 'REPLAY', 'ref': 'W2383.000.85533', 'eans': ['8053816313088']}
EX3 = {'brand': 'REPLAY', 'ref': 'M914Y.000.41A 182',
       'eans': ['8053816472044', '8053816472051', '8053816472068', '8053816472075']}

SHOP_PAGE = 'https://www.tienda-moda.example/replay-anbass-m914y00041a182.html'
SHOP_IMAGE = 'https://cdn.tienda-moda.example/img/m914y-front.jpg'


@tagged('post_install', '-at_install', 'product_auto_image')
class TestImageSearch(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env['ir.config_parameter'].sudo()
        params = {
            'request_interval': '0', 'timeout': '5', 'min_score': '60', 'max_results': '5',
            'provider': 'duckduckgo', 'max_products': '20', 'replace_existing': False, 'simulation': False,
        }
        for key, value in params.items():
            icp.set_param(f'product_auto_image.{key}', value)
        cls.size_attribute = cls.env['product.attribute'].create({
            'name': 'Talla (test auto image)',
            'create_variant': 'always',
            'value_ids': [Command.create({'name': name}) for name in ('30', '31', '32', '33')],
        })
        cls.brand = cls.env['product.brand'].create({'name': 'REPLAY'})

    def setUp(self):
        super().setUp()
        self.web = FakeWeb()

    def _create_product(self, example, **extra):
        vals = {
            'name': f'Vaquero {example["ref"]}',
            'product_brand_id': self.brand.id,
            'manufacturer_reference': example['ref'],
            **extra,
        }
        eans = example['eans']
        if len(eans) == 1:
            vals['barcode'] = eans[0]
            return self.env['product.template'].create(vals)
        vals['attribute_line_ids'] = [Command.create({
            'attribute_id': self.size_attribute.id,
            'value_ids': [Command.set(self.size_attribute.value_ids[:len(eans)].ids)],
        })]
        template = self.env['product.template'].create(vals)
        for variant, ean in zip(template.product_variant_ids, eans):
            variant.barcode = ean
        return template

    def _publish_ex3_shop(self):
        self.web.add(ddg_url('"REPLAY" "M914Y.000.41A 182"'), ddg_results_html([
            'https://www.facebook.com/replay',
            'https://www.tienda-moda.example/search?q=M914Y',
            SHOP_PAGE,
        ]))
        # La página NO contiene ningún EAN: debe encontrarse solo por referencia.
        self.web.add(SHOP_PAGE, product_page_html(
            'REPLAY Anbass M914Y.000.41A 182', og_image=SHOP_IMAGE,
            jsonld={'@context': 'https://schema.org', '@type': 'Product',
                    'brand': {'@type': 'Brand', 'name': 'REPLAY'}, 'mpn': 'M914Y.000.41A 182'},
            body='<img src="/static/logo.png">'))
        self.web.add_image(SHOP_IMAGE)

    def _logs(self, template):
        return self.env['product.auto.image.log'].search([('product_id', '=', template.id)])

    # ------------------------------------------------------------------

    def test_query_order_example1(self):
        finder = AutoImageFinder(provider=None, http=None)
        data = ProductSearchData(reference=EX1['ref'], brand=EX1['brand'], eans=EX1['eans'])
        self.assertEqual(finder.build_queries(data), [
            ('manufacturer_reference', '"REPLAY" "DK4220.000.G23726"'),
            ('manufacturer_reference', '"DK4220.000.G23726"'),
            ('ean', '"8053816464315"'),
        ])

    def test_search_data_groups_variants(self):
        template = self._create_product(EX3)
        self.assertEqual(len(template.product_variant_ids), 4)
        self.assertEqual(set(template.product_variant_ids.mapped('default_code')), {'M914Y.000.41A 182'})
        data = template._auto_image_search_data()
        self.assertEqual(data.reference, 'M914Y.000.41A 182')
        self.assertEqual(data.brand, 'REPLAY')
        self.assertEqual(sorted(data.eans), sorted(EX3['eans']))

    def test_reference_uses_default_code(self):
        single = self._create_product(EX2)
        self.assertEqual(single.default_code, 'W2383.000.85533')
        single.default_code = 'W2383.000.99999'
        self.assertEqual(single.manufacturer_reference, 'W2383.000.99999')
        variants = self._create_product(EX3)
        variants.product_variant_ids[0].default_code = 'OTRA'
        self.assertEqual(variants.manufacturer_reference, 'M914Y.000.41A 182')
        variants.manufacturer_reference = 'NUEVA.REF'
        self.assertEqual(set(variants.product_variant_ids.mapped('default_code')), {'NUEVA.REF'})

    def test_example3_found_by_reference_with_single_search(self):
        template = self._create_product(EX3)
        self._publish_ex3_shop()
        with self.web.active():
            action = template.action_auto_image_search()
        self.assertEqual(action['params']['type'], 'success')
        self.assertTrue(template.image_1920)
        self.assertEqual(template.auto_image_status, 'found')
        self.assertEqual(template.auto_image_method, 'manufacturer_reference')
        self.assertEqual(template.auto_image_confidence, 100)
        self.assertEqual(template.auto_image_source, SHOP_PAGE)
        self.assertEqual(template.auto_image_url, SHOP_IMAGE)
        # Una única búsqueda para las 4 tallas, sin recurrir a los EAN
        self.assertEqual(self.web.calls_to(DDG), [ddg_url('"REPLAY" "M914Y.000.41A 182"')])
        self.assertNotIn('https://www.tienda-moda.example/search?q=M914Y', self.web.calls)
        self.assertFalse([url for url in self.web.calls if 'facebook' in url])
        log = self._logs(template)
        self.assertEqual(len(log), 1)
        self.assertEqual((log.status, log.confidence, log.image_url), ('found', 100, SHOP_IMAGE))

    def test_example1_falls_back_to_ean(self):
        template = self._create_product(EX1)
        page = 'https://www.distribuidor.example/producto/replay-dk4220'
        image = 'https://www.distribuidor.example/media/dk4220.jpg'
        self.web.add(ddg_url('"8053816464315"'), ddg_results_html([page]))
        self.web.add(page, product_page_html(
            'REPLAY Jersey', og_image=image, jsonld={'@type': 'Product', 'gtin13': '8053816464315'}))
        self.web.add_image(image)
        with self.web.active():
            template._auto_image_process()
        self.assertEqual(self.web.calls_to(DDG), [
            ddg_url('"REPLAY" "DK4220.000.G23726"'),
            ddg_url('"DK4220.000.G23726"'),
            ddg_url('"8053816464315"'),
        ])
        self.assertEqual(template.auto_image_status, 'found')
        self.assertEqual(template.auto_image_method, 'ean')
        self.assertEqual(template.auto_image_confidence, 30 + 20 + 10 + 10)
        self.assertTrue(template.image_1920)

    def test_example2_not_found_keeps_product_untouched(self):
        template = self._create_product(EX2)
        with self.web.active():
            template._auto_image_process()
        self.assertFalse(template.image_1920)
        self.assertEqual(template.auto_image_status, 'not_found')
        log = self._logs(template)
        self.assertEqual(log.status, 'not_found')
        self.assertIn('W2383.000.85533', log.search_query)
        self.assertIn('8053816313088', log.search_query)

    def test_existing_image_not_overwritten_by_default(self):
        original = base64.b64encode(make_image('PNG', size=(300, 300)))
        template = self._create_product(EX3, image_1920=original)
        stored = template.image_1920
        self._publish_ex3_shop()
        with self.web.active():
            template._auto_image_process()
        self.assertEqual(template.image_1920, stored)
        self.assertEqual(self._logs(template).status, 'skipped')
        self.assertFalse(self.web.calls, 'No debe hacerse ninguna petición si no se va a reemplazar')

    def test_existing_image_replaced_when_requested(self):
        template = self._create_product(EX3, image_1920=base64.b64encode(make_image('PNG', size=(300, 300))))
        stored = template.image_1920
        self._publish_ex3_shop()
        with self.web.active():
            template._auto_image_process(replace_existing=True)
        self.assertNotEqual(template.image_1920, stored)
        self.assertEqual(template.auto_image_status, 'found')

    def test_simulation_does_not_modify_image(self):
        template = self._create_product(EX3)
        self._publish_ex3_shop()
        with self.web.active():
            template._auto_image_process(simulation=True)
        self.assertFalse(template.image_1920)
        self.assertEqual(template.auto_image_status, 'pending')
        self.assertEqual(template.auto_image_url, SHOP_IMAGE)
        self.assertEqual(template.auto_image_confidence, 100)
        self.assertEqual(self._logs(template).status, 'simulated')

    def test_network_error_does_not_stop_batch(self):
        failing = self._create_product(EX1)
        working = self._create_product(EX3)
        for query in ('"REPLAY" "DK4220.000.G23726"', '"DK4220.000.G23726"', '"8053816464315"'):
            self.web.add(ddg_url(query), exc=requests.ConnectionError('connection reset'))
        self._publish_ex3_shop()
        with self.web.active():
            logs = (failing | working)._auto_image_process()
        statuses = {log.product_id: log.status for log in logs}
        self.assertEqual(statuses, {failing: 'error', working: 'found'})
        self.assertEqual(failing.auto_image_status, 'error')
        self.assertIn('connection reset', failing.auto_image_error)
        self.assertTrue(working.image_1920)

    def test_timeout_is_reported(self):
        template = self._create_product(EX2)
        self.web.add(ddg_url('"REPLAY" "W2383.000.85533"'), exc=requests.Timeout('read timeout'))
        with self.web.active():
            template._auto_image_process()
        self.assertIn('Timeout', self._logs(template).notes)

    def test_cloudflare_page_is_skipped(self):
        template = self._create_product(EX3)
        blocked = 'https://www.bloqueada.example/replay-m914y00041a182.html'
        good = 'https://www.buena.example/p/replay-m914y00041a182'
        image = 'https://www.buena.example/img/m914y.webp'
        self.web.add(ddg_url('"REPLAY" "M914Y.000.41A 182"'), ddg_results_html([blocked, good]))
        self.web.add(blocked, b'<html><head><title>Just a moment...</title></head></html>', status=403,
                     headers={'Server': 'cloudflare', 'CF-RAY': '123'})
        self.web.add(good, product_page_html(
            'REPLAY M914Y.000.41A 182', og_image=image, jsonld={'@type': 'Product'}))
        self.web.add_image(image, make_image('WEBP'), content_type='image/webp')
        with self.web.active():
            template._auto_image_process()
        self.assertEqual(template.auto_image_source, good)
        self.assertEqual(template.auto_image_status, 'found')
        self.assertIn('anti-bot', self._logs(template).notes)

    def test_html_served_as_image_is_not_saved(self):
        template = self._create_product(EX3)
        self.web.add(ddg_url('"REPLAY" "M914Y.000.41A 182"'), ddg_results_html([SHOP_PAGE]))
        self.web.add(SHOP_PAGE, product_page_html(
            'REPLAY M914Y.000.41A 182', og_image=SHOP_IMAGE, jsonld={'@type': 'Product'}))
        self.web.add(SHOP_IMAGE, b'<!DOCTYPE html><html><body>Error</body></html>', content_type='image/jpeg')
        with self.web.active():
            template._auto_image_process()
        self.assertFalse(template.image_1920)
        self.assertEqual(template.auto_image_status, 'not_found')
        self.assertIn('HTML', self._logs(template).notes)

    def test_search_engine_block_is_error(self):
        template = self._create_product(EX3)
        self.web.add(
            ddg_url('"REPLAY" "M914Y.000.41A 182"'),
            b'<html><body><div class="anomaly-modal__title">bots</div><form id="challenge-form"></form></body></html>',
            status=202)
        with self.web.active():
            template._auto_image_process()
        self.assertEqual(template.auto_image_status, 'error')
        self.assertIn('DuckDuckGo', template.auto_image_error)
        self.assertEqual(len(self.web.calls_to(DDG)), 1, 'No debe insistir si el buscador bloquea')

    def test_robots_txt_is_respected(self):
        template = self._create_product(EX3)
        self._publish_ex3_shop()
        self.web.add('https://www.tienda-moda.example/robots.txt', b'User-agent: *\nDisallow: /\n',
                     content_type='text/plain')
        with self.web.active():
            template._auto_image_process()
        self.assertNotIn(SHOP_PAGE, self.web.calls)
        self.assertEqual(template.auto_image_status, 'not_found')

    def test_private_addresses_are_blocked(self):
        with self.web.active(resolved_ip='10.0.0.5'), self.assertRaises(UnsafeUrlError):
            HttpClient(min_interval=0).get('http://intranet.example/')
        with self.web.active(), self.assertRaises(UnsafeUrlError):
            HttpClient(min_interval=0).get('file:///etc/passwd')

    def test_oversized_page_is_rejected(self):
        template = self._create_product(EX3)
        self.web.add(ddg_url('"REPLAY" "M914Y.000.41A 182"'), ddg_results_html([SHOP_PAGE]))
        self.web.add(SHOP_PAGE, b'<html>' + b'a' * (4 * 1024 * 1024) + b'</html>')
        with self.web.active():
            template._auto_image_process()
        self.assertFalse(template.image_1920)
        self.assertIn('grande', self._logs(template).notes)

    def test_ddg_result_parsing(self):
        html = ddg_results_html(['https://a.example/p/1?x=1&y=2', 'https://b.example/item'],
                                ad_urls=['https://ads.example/'])
        results = DuckDuckGoHtmlProvider.parse_results(html)
        self.assertEqual([r.url for r in results], ['https://a.example/p/1?x=1&y=2', 'https://b.example/item'])

    def test_manual_image_sets_manual_status(self):
        template = self._create_product(EX2)
        template.image_1920 = base64.b64encode(make_image('PNG', size=(300, 300)))
        self.assertEqual(template.auto_image_status, 'manual')

    def test_public_user_cannot_search(self):
        template = self._create_product(EX3)
        public = self.env.ref('base.public_user')
        with self.assertRaises(AccessError):
            template.with_user(public).action_auto_image_search()

    def test_wizard_from_variants_in_simulation(self):
        template = self._create_product(EX3)
        self._publish_ex3_shop()
        wizard = self.env['product.auto.image.wizard'].with_context(
            active_model='product.product', active_ids=template.product_variant_ids.ids,
        ).create({'simulation': True})
        self.assertEqual(wizard.product_ids, template)
        with self.web.active():
            wizard.action_run()
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.log_ids.status, 'simulated')
        self.assertFalse(template.image_1920)
        self.assertEqual(len(self.web.calls_to(DDG)), 1)

    def test_reference_kept_when_variants_are_added_later(self):
        template = self.env['product.template'].create({'name': 'Vaquero', 'default_code': 'M914Y.000.41A 182'})
        template.attribute_line_ids = [Command.create({
            'attribute_id': self.size_attribute.id,
            'value_ids': [Command.set(self.size_attribute.value_ids.ids)],
        })]
        self.assertEqual(len(template.product_variant_ids), 4)
        self.assertEqual(set(template.product_variant_ids.mapped('default_code')), {'M914Y.000.41A 182'})
        self.assertEqual(template.manufacturer_reference, 'M914Y.000.41A 182')

    def test_reference_kept_when_created_with_variants(self):
        template = self.env['product.template'].create({
            'name': 'Vaquero',
            'default_code': 'DK4220.000.G23726',
            'attribute_line_ids': [Command.create({
                'attribute_id': self.size_attribute.id,
                'value_ids': [Command.set(self.size_attribute.value_ids.ids)],
            })],
        })
        self.assertEqual(set(template.product_variant_ids.mapped('default_code')), {'DK4220.000.G23726'})
        self.assertEqual(template.manufacturer_reference, 'DK4220.000.G23726')

    def test_wizard_mass_pending_in_chunks(self):
        self.env['ir.config_parameter'].sudo().set_param('product_auto_image.max_products', '2')
        self.env['product.template'].search([('auto_image_status', '=', 'pending')]).auto_image_status = 'manual'
        products = self._create_product(EX1) | self._create_product(EX2) | self._create_product(EX3)
        wizard = self.env['product.auto.image.wizard'].create({})
        self.assertEqual(wizard.scope, 'pending')
        self.assertEqual(wizard.product_count, 3)
        with self.web.active():
            wizard.action_run()
        self.assertEqual(len(wizard.log_ids), 2)
        self.assertIn('Quedan 1', wizard.summary)
        self.assertEqual(len(products.filtered(lambda p: p.auto_image_status != 'pending')), 2)

    def test_wizard_background_queues_products(self):
        template = self._create_product(EX3)
        wizard = self.env['product.auto.image.wizard'].create({
            'product_ids': [Command.set(template.ids)], 'run_in_background': True})
        wizard.action_run()
        self.assertTrue(template.auto_image_queued)
