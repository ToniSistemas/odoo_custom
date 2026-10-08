from odoo.tests import TransactionCase, tagged

from ..models import image_extractor as ex
from ..models.image_search import detect_block
from .common import make_image, product_page_html


@tagged('post_install', '-at_install', 'product_auto_image')
class TestImageExtraction(TransactionCase):

    URL = 'https://shop.example.com/replay-anbass-m914y-00041a182.html'

    def test_og_image_has_priority(self):
        html = product_page_html(
            'Replay', og_image='https://cdn.example.com/og.jpg',
            jsonld={'@context': 'https://schema.org', '@type': 'Product', 'image': 'https://cdn.example.com/ld.jpg'},
            body='<div class="product-gallery"><img src="/media/gallery1.jpg"></div><img src="/media/other.jpg">')
        analysis = ex.analyze_page(html, self.URL)
        self.assertEqual(
            [(c.url, c.origin) for c in analysis.image_candidates],
            [('https://cdn.example.com/og.jpg', 'og'),
             ('https://cdn.example.com/ld.jpg', 'jsonld'),
             ('https://shop.example.com/media/gallery1.jpg', 'gallery'),
             ('https://shop.example.com/media/other.jpg', 'img')])
        self.assertTrue(analysis.has_og_image)
        self.assertTrue(analysis.has_product_schema)

    def test_jsonld_graph_and_image_object(self):
        jsonld = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'Organization', 'logo': {'@type': 'ImageObject', 'url': 'https://x.com/brand.jpg'}},
            {'@type': ['Product'], 'name': 'Jeans', 'image': [
                {'@type': 'ImageObject', 'contentUrl': 'https://cdn.example.com/p1.jpg'},
                'https://cdn.example.com/p2.webp']},
        ]}
        analysis = ex.analyze_page(product_page_html('x', jsonld=jsonld), self.URL)
        urls = [c.url for c in analysis.image_candidates]
        self.assertEqual(urls, ['https://cdn.example.com/p1.jpg', 'https://cdn.example.com/p2.webp'])
        self.assertTrue(analysis.has_product_schema)
        self.assertFalse(analysis.has_og_image)

    def test_gallery_lazy_attributes_and_filters(self):
        body = '''
            <header><img src="/static/logo.png" alt="Shop"></header>
            <img src="/icons/cart.png">
            <img src="/img/tiny.jpg" width="40" height="40">
            <img src="data:image/gif;base64,R0lGOD" class="lazy">
            <img src="/img/banner-sale.jpg">
            <div id="pdp-gallery">
              <img src="data:image/png;base64,xx" data-src="/img/main-lazy.jpg">
              <img srcset="/img/s-400.jpg 400w, /img/s-1200.jpg 1200w" src="/img/s-400.jpg">
              <img src="/img/z-small.jpg" data-zoom-image="/img/z-big.jpg">
            </div>
            <img src="/img/payment-visa.svg">'''
        analysis = ex.analyze_page(product_page_html('x', body=body), self.URL)
        urls = [c.url for c in analysis.image_candidates]
        self.assertEqual(urls, [
            'https://shop.example.com/img/main-lazy.jpg',
            'https://shop.example.com/img/s-1200.jpg',
            'https://shop.example.com/img/z-big.jpg',
        ])
        self.assertTrue(all(c.origin == 'gallery' for c in analysis.image_candidates))

    def test_reference_normalization(self):
        self.assertEqual(ex.normalize_code('M914Y.000.41A 182'), 'm914y00041a182')
        html = product_page_html('Vaqueros', body='<p>Ref: M914Y 000 41A182</p><p>Marca: Replay</p>')
        score = ex.score_page(ex.analyze_page(html, 'https://shop.example.com/jeans'), 'M914Y.000.41A 182', 'REPLAY')
        self.assertTrue(score.reference_found)
        self.assertTrue(score.brand_found)
        self.assertEqual(score.score, ex.SCORE_REFERENCE + ex.SCORE_BRAND)

    def test_full_product_page_score(self):
        html = product_page_html(
            'REPLAY M914Y.000.41A 182', og_image='https://cdn.example.com/og.jpg',
            jsonld={'@type': 'Product', 'gtin13': '8053816472044'})
        score = ex.score_page(ex.analyze_page(html, self.URL), 'M914Y.000.41A 182', 'REPLAY', ['8053816472044'])
        self.assertEqual(score.score, 50 + 30 + 20 + 10 + 10)

    def test_ean_needs_digit_boundaries(self):
        html = product_page_html('x', body='<p>Código 98053816472044 1</p>')
        analysis = ex.analyze_page(html, self.URL)
        self.assertFalse(ex.score_page(analysis, eans=['8053816472044']).ean_found)
        analysis = ex.analyze_page(product_page_html('x', body='<p>EAN: 08053816472044</p>'), self.URL)
        self.assertTrue(ex.score_page(analysis, eans=['8053816472044']).ean_found)

    def test_category_page_penalty(self):
        jsonld = {'@type': 'ItemList', 'itemListElement': [
            {'@type': 'ListItem', 'position': i, 'url': f'https://shop.example.com/p{i}'} for i in range(10)]}
        html = product_page_html('Vaqueros REPLAY hombre', jsonld=jsonld, body='M914Y.000.41A 182')
        analysis = ex.analyze_page(html, 'https://shop.example.com/c/vaqueros-replay')
        self.assertTrue(analysis.is_category)
        score = ex.score_page(analysis, 'M914Y.000.41A 182', 'REPLAY')
        self.assertEqual(score.score, 50 + 30 - 50)

    def test_search_results_page_penalty(self):
        html = product_page_html('Resultados de búsqueda', body='M914Y.000.41A 182 REPLAY')
        analysis = ex.analyze_page(html, 'https://shop.example.com/search?q=M914Y.000.41A+182')
        self.assertTrue(analysis.is_search_results)
        self.assertEqual(ex.score_page(analysis, 'M914Y.000.41A 182', 'REPLAY').score, 50 + 30 - 50)

    def test_invalid_html_does_not_crash(self):
        self.assertEqual(ex.analyze_page(b'', self.URL).image_candidates, [])
        self.assertEqual(ex.analyze_page(b'\x00\x01\x02', self.URL).image_candidates, [])

    # ------------------------------------------------------------------ imágenes

    def test_valid_jpeg_and_png(self):
        image = ex.validate_image(make_image('JPEG'), 'image/jpeg', 10 * 1024 * 1024)
        self.assertEqual((image.mimetype, image.width, image.height), ('image/jpeg', 800, 800))
        self.assertFalse(image.is_small())
        image = ex.validate_image(make_image('PNG'), 'image/png; charset=binary')
        self.assertEqual(image.mimetype, 'image/png')

    def test_webp_is_converted(self):
        image = ex.validate_image(make_image('WEBP'), 'image/webp')
        self.assertTrue(image.converted)
        self.assertEqual(image.mimetype, 'image/jpeg')
        self.assertEqual(ex.sniff_image_format(image.data), 'JPEG')
        image = ex.validate_image(make_image('WEBP', mode='RGBA'), 'image/webp')
        self.assertEqual(image.mimetype, 'image/png')

    def test_octet_stream_accepted_by_signature(self):
        image = ex.validate_image(make_image('JPEG'), 'application/octet-stream')
        self.assertEqual(image.mimetype, 'image/jpeg')

    def test_html_disguised_as_image_is_rejected(self):
        html = b'<!DOCTYPE html><html><head><title>Just a moment...</title></head></html>'
        with self.assertRaisesRegex(ex.InvalidImageError, 'HTML'):
            ex.validate_image(html, 'image/jpeg')
        with self.assertRaisesRegex(ex.InvalidImageError, 'Content-Type'):
            ex.validate_image(make_image('JPEG'), 'text/html; charset=utf-8')

    def test_corrupted_and_unsupported_images_rejected(self):
        with self.assertRaises(ex.InvalidImageError):
            ex.validate_image(b'\xff\xd8\xff' + b'garbage' * 20, 'image/jpeg')
        with self.assertRaises(ex.InvalidImageError):
            ex.validate_image(make_image('GIF'), 'image/gif')
        with self.assertRaises(ex.InvalidImageError):
            ex.validate_image(make_image('GIF'), 'application/octet-stream')
        with self.assertRaises(ex.InvalidImageError):
            ex.validate_image(b'', 'image/jpeg')

    def test_size_limit(self):
        data = make_image('PNG', size=(1000, 1000))
        with self.assertRaisesRegex(ex.InvalidImageError, 'tamaño máximo'):
            ex.validate_image(data, 'image/png', max_bytes=len(data) - 1)

    def test_small_image_flag(self):
        image = ex.validate_image(make_image('JPEG', size=(120, 120)), 'image/jpeg')
        self.assertTrue(image.is_small())

    # ------------------------------------------------------------------ bloqueos

    def test_detect_cloudflare_block(self):
        body = b'<html><head><title>Just a moment...</title></head><body>cf-browser-verification</body></html>'
        self.assertTrue(detect_block(403, {'Server': 'cloudflare', 'CF-RAY': '1'}, body))
        self.assertTrue(detect_block(200, {}, body))
        self.assertTrue(detect_block(503, {'cf-ray': 'x'}, b'error'))
        self.assertTrue(detect_block(429, {}, b''))
        self.assertTrue(detect_block(200, {'cf-mitigated': 'challenge'}, b''))

    def test_normal_page_not_detected_as_block(self):
        body = b'<html><script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script><h1>Jeans</h1></html>'
        self.assertIsNone(detect_block(200, {'Server': 'cloudflare'}, body))
        self.assertIsNone(detect_block(404, {}, b'not found'))
