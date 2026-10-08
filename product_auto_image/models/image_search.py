"""Cliente HTTP prudente, proveedores de búsqueda web y motor de búsqueda de imágenes.

Flujo: REFERENCIA FABRICANTE -> búsqueda web -> ficha de producto -> imagen
       (fallback) EAN -> búsqueda web -> ficha de producto -> imagen
"""
import ipaddress
import json
import logging
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import requests
from lxml import etree
from lxml import html as lxml_html

from . import image_extractor as extractor

_logger = logging.getLogger(__name__)

ROBOTS_AGENT = 'OdooProductAutoImage'
DEFAULT_USER_AGENT = (
    f'Mozilla/5.0 (compatible; {ROBOTS_AGENT}/1.0; consulta puntual de imagenes de producto)'
)
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_ROBOTS_BYTES = 512 * 1024
MAX_REDIRECTS = 5
IMAGE_ACCEPT = 'image/webp,image/png,image/jpeg;q=0.9,*/*;q=0.5'
HTML_ACCEPT = 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.5'


class AutoImageError(Exception):
    """Error controlado durante la búsqueda (no detiene el lote)."""


class NetworkError(AutoImageError):
    pass


class BlockedError(AutoImageError):
    pass


class RobotsDisallowedError(AutoImageError):
    pass


class ResponseTooLargeError(AutoImageError):
    pass


class UnsafeUrlError(AutoImageError):
    pass


class SearchProviderError(AutoImageError):
    pass


# ---------------------------------------------------------------------------
# Detección de bloqueos (Cloudflare, DataDome, PerimeterX, captchas...)
# ---------------------------------------------------------------------------

_STRONG_BLOCK_MARKERS = (
    b'<title>just a moment', b'cf_chl_opt', b'cf-browser-verification', b'attention required! | cloudflare',
    b'checking your browser before', b'captcha-delivery.com', b'px-captcha', b'/cdn-cgi/challenge-platform/h/',
)
_WEAK_BLOCK_MARKERS = _STRONG_BLOCK_MARKERS + (
    b'challenge-platform', b'datadome', b'perimeterx', b'are you a robot', b'g-recaptcha', b'hcaptcha',
    b'access denied', b'request blocked', b'bot detection',
)


def detect_block(status, headers, body):
    """Devuelve el motivo si la respuesta es un bloqueo anti-bot, o None."""
    headers = {k.lower(): v for k, v in (headers or {}).items()}
    sample = (body or b'')[:30000].lower()
    is_cloudflare = 'cloudflare' in headers.get('server', '').lower() or 'cf-ray' in headers
    if headers.get('cf-mitigated'):
        return 'Desafío Cloudflare'
    if status == 429:
        return 'Límite de peticiones alcanzado (HTTP 429)'
    if status in (401, 403, 503) and (is_cloudflare or any(m in sample for m in _WEAK_BLOCK_MARKERS)):
        return f'Bloqueo anti-bot (HTTP {status}{", Cloudflare" if is_cloudflare else ""})'
    if status < 400 and any(m in sample for m in _STRONG_BLOCK_MARKERS):
        return 'Página de verificación anti-bot'
    return None


@dataclass
class HttpResponse:
    url: str
    status: int
    headers: dict
    content: bytes

    @property
    def content_type(self):
        return (self.headers.get('content-type') or '').split(';', 1)[0].strip().lower()


class HttpClient:
    """Cliente HTTP secuencial con timeout, límite de tamaño, rate limit por host,
    robots.txt y protección SSRF (no accede a IPs privadas)."""

    _throttle_lock = threading.Lock()
    _last_request_by_host = {}
    _robots_cache = {}
    ROBOTS_TTL = 3600
    ROBOTS_CACHE_SIZE = 500

    def __init__(self, timeout=10, min_interval=2.0, user_agent=None, respect_robots=True, session=None):
        self.timeout = timeout
        self.min_interval = max(float(min_interval or 0), 0.0)
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.respect_robots = respect_robots
        self.session = session or requests.Session()
        self.session.headers.update({
            'User-Agent': self.user_agent,
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.7',
        })

    @staticmethod
    def resolve_host(host):
        return [info[4][0] for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)]

    def _check_url(self, url, allow_private):
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            raise UnsafeUrlError(f'URL no permitida: {url}')
        if allow_private:
            return
        try:
            addresses = self.resolve_host(parsed.hostname)
        except (socket.gaierror, UnicodeError) as exc:
            raise NetworkError(f'No se puede resolver {parsed.hostname}: {exc}') from exc
        for address in addresses:
            if not ipaddress.ip_address(address.split('%', 1)[0]).is_global:
                raise UnsafeUrlError(f'Dirección no pública bloqueada: {parsed.hostname} ({address})')

    def _throttle(self, host):
        if self.min_interval <= 0:
            return
        with HttpClient._throttle_lock:
            now = time.monotonic()
            last = HttpClient._last_request_by_host.get(host, 0.0)
            slot = max(now, last + self.min_interval)
            HttpClient._last_request_by_host[host] = slot
        if slot > now:
            time.sleep(slot - now)

    def _request(self, url, *, max_bytes, accept=None, check_robots=True, allow_private=False, data=None):
        current, method = url, 'POST' if data is not None else 'GET'
        for _hop in range(MAX_REDIRECTS + 1):
            self._check_url(current, allow_private)
            if check_robots and self.respect_robots and not self.robots_allowed(current):
                raise RobotsDisallowedError(f'robots.txt no permite acceder a {current}')
            self._throttle(urlparse(current).netloc.lower())
            try:
                resp = self.session.request(
                    method, current, headers={'Accept': accept} if accept else None, data=data,
                    timeout=self.timeout, stream=True, allow_redirects=False)
            except requests.Timeout as exc:
                raise NetworkError(f'Timeout ({self.timeout}s) en {current}') from exc
            except requests.RequestException as exc:
                raise NetworkError(f'Error de red en {current}: {exc}') from exc
            try:
                location = resp.headers.get('Location')
                if resp.status_code in (301, 302, 303, 307, 308) and location:
                    current, method, data = urljoin(current, location), 'GET', None
                    continue
                return self._read(resp, current, max_bytes)
            finally:
                resp.close()
        raise NetworkError(f'Demasiadas redirecciones desde {url}')

    @staticmethod
    def _read(resp, url, max_bytes):
        headers = {k.lower(): v for k, v in resp.headers.items()}
        length = (headers.get('content-length') or '').strip()
        if max_bytes and length.isdigit() and int(length) > max_bytes:
            raise ResponseTooLargeError(f'Respuesta demasiado grande ({length} bytes) en {url}')
        chunks, total = [], 0
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                total += len(chunk)
                if max_bytes and total > max_bytes:
                    raise ResponseTooLargeError(f'Respuesta demasiado grande (más de {max_bytes} bytes) en {url}')
                chunks.append(chunk)
        except requests.RequestException as exc:
            raise NetworkError(f'Error leyendo {url}: {exc}') from exc
        return HttpResponse(url=url, status=resp.status_code, headers=headers, content=b''.join(chunks))

    def get(self, url, *, max_bytes=MAX_PAGE_BYTES, accept=None, check_robots=True, allow_private=False,
            data=None):
        """GET (o POST de formulario si se pasa ``data``) seguro.
        Lanza BlockedError / NetworkError si la respuesta no es utilizable."""
        resp = self._request(
            url, max_bytes=max_bytes, accept=accept, check_robots=check_robots,
            allow_private=allow_private, data=data)
        reason = detect_block(resp.status, resp.headers, resp.content)
        if reason:
            raise BlockedError(f'{reason}: {resp.url}')
        if resp.status >= 400:
            raise NetworkError(f'HTTP {resp.status} en {resp.url}')
        return resp

    def robots_allowed(self, url):
        parsed = urlparse(url)
        key = f'{parsed.scheme}://{parsed.netloc}'.lower()
        now = time.monotonic()
        cached = HttpClient._robots_cache.get(key)
        if cached and cached[0] > now:
            parser = cached[1]
        else:
            parser = self._fetch_robots(key)
            if len(HttpClient._robots_cache) >= self.ROBOTS_CACHE_SIZE:
                HttpClient._robots_cache.clear()
            HttpClient._robots_cache[key] = (now + self.ROBOTS_TTL, parser)
        return parser.can_fetch(ROBOTS_AGENT, url)

    def _fetch_robots(self, origin):
        parser = robotparser.RobotFileParser(f'{origin}/robots.txt')
        try:
            resp = self._request(
                f'{origin}/robots.txt', max_bytes=MAX_ROBOTS_BYTES, accept='text/plain', check_robots=False)
        except AutoImageError as exc:
            _logger.debug('robots.txt no disponible en %s: %s', origin, exc)
            parser.allow_all = True
            return parser
        if resp.status in (401, 403):
            parser.disallow_all = True
        elif resp.status >= 400:
            parser.allow_all = True
        else:
            parser.parse(resp.content.decode('utf-8', 'replace').splitlines())
        return parser


# ---------------------------------------------------------------------------
# Proveedores de búsqueda
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    url: str
    title: str = ''
    snippet: str = ''


SEARCH_PROVIDERS = {}


def register_provider(cls):
    SEARCH_PROVIDERS[cls.code] = cls
    return cls


def get_provider(code, http, **options):
    provider_cls = SEARCH_PROVIDERS.get(code)
    if not provider_cls:
        raise SearchProviderError(f'Proveedor de búsqueda desconocido: {code}')
    return provider_cls(http, **options)


class ImageSearchProvider:
    """Interfaz de proveedor de búsqueda web. Para añadir uno nuevo, heredar,
    definir ``code``/``label``, implementar ``search`` y decorar con ``@register_provider``."""

    code = None
    label = None

    def __init__(self, http, **options):
        self.http = http
        self.options = options

    def prepare_query(self, query):
        """Adapta la consulta lógica (con frases entre comillas) a la sintaxis del buscador."""
        return query

    def search(self, query, max_results=10):
        """Devuelve una lista de :class:`SearchResult`."""
        raise NotImplementedError


@register_provider
class DuckDuckGoHtmlProvider(ImageSearchProvider):
    """Versión HTML pública de DuckDuckGo (sin JavaScript ni API key), usando su
    formulario POST nativo.

    Pensado para volúmenes bajos y espaciados. Si DuckDuckGo muestra un desafío
    anti-bot se lanza BlockedError y conviene usar otro proveedor (p. ej. SearXNG)."""

    code = 'duckduckgo'
    label = 'DuckDuckGo (HTML público)'
    endpoint = 'https://html.duckduckgo.com/html/'

    def prepare_query(self, query):
        # DuckDuckGo HTML no devuelve resultados para frases exactas con puntos ("M914Y.000.41A 182").
        return ' '.join(query.replace('"', ' ').split())

    def build_form(self, query):
        return {'q': query, 'kl': self.options.get('region') or 'es-es'}

    def search(self, query, max_results=10):
        resp = self.http.get(
            self.endpoint, data=self.build_form(query), accept=HTML_ACCEPT, check_robots=False)
        results = self.parse_results(resp.content, max_results)
        if not results and (resp.status == 202 or b'anomaly' in resp.content or b'challenge-form' in resp.content):
            raise BlockedError('DuckDuckGo ha solicitado verificación anti-bot; reintente más tarde o use otro proveedor')
        return results

    @staticmethod
    def decode_href(href):
        if not href:
            return None
        if href.startswith('//'):
            href = 'https:' + href
        elif href.startswith('/'):
            href = 'https://duckduckgo.com' + href
        parsed = urlparse(href)
        if parsed.netloc.endswith('duckduckgo.com'):
            if parsed.path.startswith('/l/'):
                target = parse_qs(parsed.query).get('uddg')
                return target[0] if target else None
            return None  # anuncios (y.js) u otros enlaces internos
        return href if parsed.scheme in ('http', 'https') else None

    @classmethod
    def parse_results(cls, content, max_results=10):
        try:
            tree = lxml_html.document_fromstring(content)
        except (etree.LxmlError, ValueError):
            return []
        results, seen = [], set()
        for link in tree.xpath('//a[contains(concat(" ", normalize-space(@class), " "), " result__a ")]'):
            container = link.xpath(
                'ancestor::div[contains(concat(" ", normalize-space(@class), " "), " result ")][1]')
            if container and 'result--ad' in (container[0].get('class') or ''):
                continue
            url = cls.decode_href(link.get('href'))
            if not url or url in seen:
                continue
            seen.add(url)
            snippet = ''
            if container:
                snippet = ' '.join(container[0].xpath('string(.//*[contains(@class, "result__snippet")])').split())
            results.append(SearchResult(url=url, title=' '.join(link.text_content().split()), snippet=snippet))
            if len(results) >= max_results:
                break
        return results


@register_provider
class SearxngProvider(ImageSearchProvider):
    """Instancia SearXNG (metabuscador libre, autoalojable) con salida JSON habilitada."""

    code = 'searxng'
    label = 'SearXNG (instancia propia)'

    def search(self, query, max_results=10):
        base = (self.options.get('searxng_url') or '').strip().rstrip('/')
        if not base:
            raise SearchProviderError('Configure la URL de la instancia SearXNG en Ajustes')
        params = {'q': query, 'format': 'json', 'language': self.options.get('language') or 'es-ES'}
        # La URL la define el administrador: se permite una instancia en red local.
        resp = self.http.get(
            f'{base}/search?{urlencode(params)}', accept='application/json',
            check_robots=False, allow_private=True)
        try:
            data = json.loads(resp.content.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as exc:
            raise SearchProviderError('SearXNG no devolvió JSON (¿está habilitado format=json?)') from exc
        results = []
        for item in data.get('results') or []:
            url = item.get('url')
            if url and urlparse(url).scheme in ('http', 'https'):
                results.append(SearchResult(url=url, title=item.get('title') or '', snippet=item.get('content') or ''))
            if len(results) >= max_results:
                break
        return results


# ---------------------------------------------------------------------------
# Motor de búsqueda de imágenes
# ---------------------------------------------------------------------------

_SKIP_RESULT_HOST_RE = re.compile(
    r'(^|\.)(duckduckgo\.com|google\.[a-z.]+|bing\.com|yahoo\.com|youtube\.com|youtu\.be|facebook\.com|'
    r'instagram\.com|pinterest\.[a-z.]+|twitter\.com|x\.com|tiktok\.com|reddit\.com|wikipedia\.org|'
    r'linkedin\.com|amazon\.[a-z.]+|ebay\.[a-z.]+)$',
    re.IGNORECASE,
)
_SKIP_RESULT_EXT = ('.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.zip')
_PRODUCT_URL_RE = re.compile(
    r'(/p/|/dp/|/product|/producto|/articulo|/item|/prod\b|\.html?$|[-_/]\d{5,})', re.IGNORECASE)


@dataclass
class ProductSearchData:
    reference: str = ''
    brand: str = ''
    eans: list = field(default_factory=list)
    name: str = ''


@dataclass
class FinderSettings:
    min_score: int = 60
    max_results: int = 5
    max_image_bytes: int = 5 * 1024 * 1024
    max_images_per_page: int = 3
    max_eans: int = 3
    min_image_side: int = extractor.MIN_IMAGE_SIDE


@dataclass
class Candidate:
    page_url: str
    method: str
    query: str
    page_score: int = 0
    confidence: int = 0
    image_url: str = None
    image: extractor.ValidatedImage = None
    reasons: list = field(default_factory=list)


@dataclass
class FinderResult:
    status: str = 'not_found'  # found | not_found | error
    method: str = None
    queries: list = field(default_factory=list)
    candidate: Candidate = None
    error: str = ''
    notes: list = field(default_factory=list)

    @property
    def search_query(self):
        return ' | '.join(self.queries)


class AutoImageFinder:

    def __init__(self, provider, http, settings=None):
        self.provider = provider
        self.http = http
        self.settings = settings or FinderSettings()

    @staticmethod
    def _clean(value):
        return ' '.join((value or '').replace('"', ' ').split())

    def build_queries(self, product):
        """Lista ordenada de (método, consulta): primero referencia, después EAN."""
        reference, brand = self._clean(product.reference), self._clean(product.brand)
        queries = []
        if reference:
            if brand:
                queries.append(('manufacturer_reference', f'"{brand}" "{reference}"'))
            queries.append(('manufacturer_reference', f'"{reference}"'))
        for ean in (product.eans or [])[:self.settings.max_eans]:
            queries.append(('ean', f'"{ean}"'))
        return queries

    def rank_results(self, results, product):
        """Descarta dominios irrelevantes y prioriza lo que parece una ficha de producto."""
        norm_ref = extractor.normalize_code(product.reference)
        ranked = []
        for index, result in enumerate(results):
            parsed = urlparse(result.url)
            host = (parsed.hostname or '').lower()
            if not host or _SKIP_RESULT_HOST_RE.search(host) or parsed.path.lower().endswith(_SKIP_RESULT_EXT):
                continue
            haystack = f'{result.url} {result.title} {result.snippet}'
            score = 0
            if norm_ref and norm_ref in extractor.normalize_code(haystack):
                score += 3
            if any(ean in haystack for ean in product.eans or ()):
                score += 2
            if _PRODUCT_URL_RE.search(parsed.path):
                score += 1
            if extractor.looks_like_search_url(result.url):
                score -= 4
            ranked.append((score, index, result))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [item[2] for item in ranked]

    def _acceptable(self, candidate):
        return bool(candidate and candidate.image and candidate.confidence >= self.settings.min_score)

    @staticmethod
    def _rank_key(candidate):
        return (candidate.image is not None, candidate.confidence)

    def evaluate_page(self, url, product, method, query, notes):
        try:
            resp = self.http.get(url, accept=HTML_ACCEPT)
        except AutoImageError as exc:
            notes.append(f'  - {url}: {exc}')
            return None
        if resp.content_type and 'html' not in resp.content_type:
            notes.append(f'  - {url}: no es HTML ({resp.content_type})')
            return None

        analysis = extractor.analyze_page(resp.content, resp.url)
        scoring = extractor.score_page(analysis, product.reference, product.brand, product.eans)
        page = Candidate(
            page_url=resp.url, method=method, query=query, page_score=scoring.score,
            confidence=scoring.score, reasons=list(scoring.reasons))
        notes.append(f'  - {resp.url}: puntuación {scoring.score} ({", ".join(scoring.reasons) or "sin coincidencias"})')
        if scoring.score < self.settings.min_score:
            return page  # una imagen solo puede restar puntos: no se descarga

        fallback = None
        for image_candidate in analysis.image_candidates[:self.settings.max_images_per_page]:
            try:
                img_resp = self.http.get(
                    image_candidate.url, max_bytes=self.settings.max_image_bytes, accept=IMAGE_ACCEPT)
                image = extractor.validate_image(img_resp.content, img_resp.content_type, self.settings.max_image_bytes)
            except (AutoImageError, extractor.InvalidImageError) as exc:
                notes.append(f'    imagen descartada {image_candidate.url}: {exc}')
                continue
            option = Candidate(
                page_url=resp.url, method=method, query=query, page_score=scoring.score,
                confidence=scoring.score, image_url=image_candidate.url, image=image,
                reasons=page.reasons + [f'imagen {image.width}x{image.height} ({image_candidate.origin})'])
            if not image.is_small(self.settings.min_image_side):
                return option
            option.confidence += extractor.PENALTY_SMALL_IMAGE
            option.reasons.append(f'{extractor.PENALTY_SMALL_IMAGE} imagen demasiado pequeña')
            fallback = fallback or option
        if not fallback:
            notes.append('    ninguna imagen válida en la página')
        return fallback or page

    def find(self, product):
        result = FinderResult()
        queries = self.build_queries(product)
        if not queries:
            result.error = 'El producto no tiene referencia de fabricante ni EAN'
            return result

        best, visited, search_errors, searched_ok = None, set(), [], False
        for method, logical_query in queries:
            query = self.provider.prepare_query(logical_query)
            if query in result.queries:
                continue
            result.queries.append(query)
            result.method = method
            try:
                results = self.provider.search(query, self.settings.max_results * 2)
            except AutoImageError as exc:
                search_errors.append(str(exc))
                result.notes.append(f'[{query}] error de búsqueda: {exc}')
                if isinstance(exc, BlockedError):
                    break  # el buscador nos está bloqueando: no insistir
                continue
            searched_ok = True
            ranked = self.rank_results(results, product)[:self.settings.max_results]
            result.notes.append(f'[{query}] {len(results)} resultados, {len(ranked)} candidatos')
            for search_result in ranked:
                if search_result.url in visited:
                    continue
                visited.add(search_result.url)
                candidate = self.evaluate_page(search_result.url, product, method, query, result.notes)
                if candidate and (best is None or self._rank_key(candidate) > self._rank_key(best)):
                    best = candidate
                if self._acceptable(best):
                    break
            if self._acceptable(best):
                result.status, result.method, result.candidate = 'found', best.method, best
                return result

        result.candidate = best
        if best:
            result.method = best.method
        if not searched_ok and search_errors:
            result.status = 'error'
            result.error = '; '.join(search_errors)
        else:
            result.error = 'No se encontró ninguna imagen con confianza suficiente'
            if best:
                result.error += f' (mejor puntuación {best.confidence} en {best.page_url})'
        return result
