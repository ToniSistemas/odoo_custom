"""Utilidades de test: web simulada (sin acceso real a Internet)."""
import io
import json
from contextlib import contextmanager
from unittest.mock import patch
from urllib.parse import quote

import requests
from requests.structures import CaseInsensitiveDict
from PIL import Image

from ..models.image_search import DuckDuckGoHtmlProvider, HttpClient


def make_image(fmt='JPEG', size=(800, 800), mode='RGB'):
    buffer = io.BytesIO()
    Image.new(mode, size, (200, 30, 30, 128)[:len(mode)]).save(buffer, format=fmt)
    return buffer.getvalue()


def ddg_url(query):
    """Clave de la petición POST a DuckDuckGo en :class:`FakeWeb`."""
    return f'{DuckDuckGoHtmlProvider.endpoint}#q={DuckDuckGoHtmlProvider(None).prepare_query(query)}'


def ddg_results_html(urls, ad_urls=()):
    items = []
    for url in ad_urls:
        items.append(
            '<div class="result results_links result--ad"><a class="result__a" '
            f'href="https://duckduckgo.com/y.js?ad_domain=x&amp;u3={quote(url, safe="")}">Ad</a></div>')
    for index, url in enumerate(urls):
        items.append(
            '<div class="result results_links results_links_deep web-result">'
            f'<h2 class="result__title"><a class="result__a" rel="nofollow" '
            f'href="//duckduckgo.com/l/?uddg={quote(url, safe="")}&amp;rut=abc{index}">Resultado {index}</a></h2>'
            f'<a class="result__snippet" href="#">Snippet {index}</a></div>')
    if not items:
        items.append('<div class="no-results">No results.</div>')
    return f'<html><body><div id="links">{"".join(items)}</div></body></html>'.encode()


def product_page_html(title, og_image=None, jsonld=None, body='', extra_head=''):
    head = [f'<title>{title}</title>', extra_head]
    if og_image:
        head.append('<meta property="og:type" content="product">')
        head.append(f'<meta property="og:image" content="{og_image}">')
    if jsonld:
        head.append(f'<script type="application/ld+json">{json.dumps(jsonld)}</script>')
    return f'<html><head>{"".join(head)}</head><body>{body}</body></html>'.encode()


def make_response(url, status=200, body=b'', content_type='text/html; charset=utf-8', headers=None):
    response = requests.Response()
    response.status_code = status
    response.url = url
    response.headers = CaseInsensitiveDict(headers or {})
    if content_type:
        response.headers.setdefault('Content-Type', content_type)
    response._content = body
    response._content_consumed = True
    response.encoding = 'utf-8'
    return response


class FakeWeb:
    """Router de URLs -> respuestas. Las URLs no registradas devuelven 404."""

    def __init__(self):
        self.routes = {}
        self.calls = []

    def add(self, url, body=b'', status=200, content_type='text/html; charset=utf-8', headers=None, exc=None):
        self.routes[url] = {
            'body': body, 'status': status, 'content_type': content_type, 'headers': headers, 'exc': exc}

    def add_image(self, url, data=None, content_type='image/jpeg'):
        self.add(url, data if data is not None else make_image(), content_type=content_type)

    def calls_to(self, prefix):
        return [url for url in self.calls if url.startswith(prefix)]

    def handle(self, method, url, **kwargs):
        data = kwargs.get('data')
        key = f"{url}#q={data['q']}" if data else url
        self.calls.append(key)
        route = self.routes.get(key)
        if route is None and url.startswith(DuckDuckGoHtmlProvider.endpoint):
            return make_response(url, 200, ddg_results_html([]))
        if route is None:
            return make_response(url, 404, b'not found', 'text/plain')
        if route['exc']:
            raise route['exc']
        return make_response(url, route['status'], route['body'], route['content_type'], route['headers'])

    @contextmanager
    def active(self, resolved_ip='93.184.216.34'):
        web = self

        def fake_request(session, method, url, **kwargs):
            return web.handle(method, url, **kwargs)

        HttpClient._robots_cache.clear()
        HttpClient._last_request_by_host.clear()
        with patch.object(requests.Session, 'request', fake_request), \
                patch.object(HttpClient, 'resolve_host', staticmethod(lambda host: [resolved_ip])):
            yield self
