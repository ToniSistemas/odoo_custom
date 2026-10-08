"""Análisis de fichas de producto, puntuación de confianza y validación de imágenes.

Este módulo no depende del ORM de Odoo para poder probarse de forma aislada.
"""
import io
import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urljoin, urlparse

from lxml import etree
from lxml import html as lxml_html
from PIL import Image

try:
    # Odoo limita los plugins de PIL que se cargan; WEBP debe registrarse explícitamente.
    from PIL import WebPImagePlugin  # noqa: F401
except ImportError:  # Pillow compilado sin libwebp
    WebPImagePlugin = None

_logger = logging.getLogger(__name__)

# Puntuación de confianza
SCORE_REFERENCE = 50
SCORE_BRAND = 30
SCORE_EAN = 20
SCORE_SCHEMA_PRODUCT = 10
SCORE_OG_IMAGE = 10
PENALTY_CATEGORY = -50
PENALTY_SEARCH_RESULTS = -50
PENALTY_SMALL_IMAGE = -30

MIN_IMAGE_SIDE = 200
MIN_IMG_ATTR_SIZE = 150
MAX_IMAGE_PIXELS = 40_000_000
MAX_CANDIDATES = 12

MIMETYPE_BY_FORMAT = {'JPEG': 'image/jpeg', 'PNG': 'image/png', 'WEBP': 'image/webp'}
ALLOWED_CONTENT_TYPES = {
    'image/jpeg', 'image/jpg', 'image/pjpeg', 'image/png', 'image/x-png', 'image/webp',
}
# Algunos CDN sirven imágenes con un tipo genérico: se aceptan si la firma binaria es válida.
GENERIC_CONTENT_TYPES = {'', 'application/octet-stream', 'binary/octet-stream'}

_SKIP_IMAGE_RE = re.compile(
    r'(?<![a-z])(logos?|icons?|favicons?|sprites?|banners?|placeholders?|payments?|paypal|visa|mastercard|'
    r'klarna|flags?|badges?|avatars?|loader|loading|spinner|blank|pixel|spacer|tracking|advert\w*|ads|'
    r'promos?|newsletter|social|facebook|twitter|instagram|pinterest|youtube|tiktok|whatsapp|'
    r'trustpilot|ratings?|cookies?|captcha|qr)(?![a-z])',
    re.IGNORECASE,
)
_SKIP_IMAGE_EXT = ('.svg', '.gif', '.ico', '.bmp', '.tif', '.tiff')
_GALLERY_RE = re.compile(
    r'gallery|galeria|product[-_]?(image|media|photo|img|picture|gallery)|pdp|carousel|swiper|slick|'
    r'slider|zoom|main[-_]?image|fotorama|lightbox|primary[-_]?image',
    re.IGNORECASE,
)
_SEARCH_PATH_RE = re.compile(
    r'/(search|buscar|busqueda|búsqueda|resultados|catalogsearch|suche|recherche|ricerca|find)(?:[/.?]|$)',
    re.IGNORECASE,
)
_SEARCH_QUERY_KEYS = {
    'q', 's', 'query', 'search', 'searchterm', 'search_query', 'k', 'keyword', 'keywords', 'text', 'term',
}
_CATEGORY_PATH_RE = re.compile(
    r'/(c|category|categories|categoria|categorias|categoría|collections?|catalog|catalogo|catálogo|'
    r'brands?|marcas?|listing|outlet|rebajas)(?:/|$)',
    re.IGNORECASE,
)
_SEARCH_TITLE_RE = re.compile(
    r'search results|results for|resultados de (la )?b[uú]squeda|resultados para|no se han encontrado',
    re.IGNORECASE,
)
_PRODUCT_TYPES = {'product', 'productgroup', 'individualproduct', 'productmodel', 'somproducts'}
_JSONLD_SKIP_KEYS = {
    'logo', 'publisher', 'brand', 'author', 'breadcrumb', 'seller', 'manufacturer', 'review',
    'aggregateRating', 'potentialAction', 'creator', 'isPartOf',
}
_IMG_PRIMARY_ATTRS = (
    'data-zoom-image', 'data-large_image', 'data-large-image', 'data-zoom', 'data-full', 'data-full-src',
)
_IMG_LAZY_ATTRS = ('data-original', 'data-src', 'data-lazy-src', 'data-lazy', 'src')


class InvalidImageError(Exception):
    """El contenido descargado no es una imagen aceptable."""


@dataclass
class ImageCandidate:
    url: str
    origin: str  # og | jsonld | gallery | img


@dataclass
class PageAnalysis:
    url: str
    title: str = ''
    text: str = ''
    norm_text: str = ''
    og_type: str = ''
    has_og_image: bool = False
    has_product_schema: bool = False
    is_category: bool = False
    is_search_results: bool = False
    image_candidates: list = field(default_factory=list)


@dataclass
class ScoreResult:
    score: int = 0
    reference_found: bool = False
    brand_found: bool = False
    ean_found: bool = False
    reasons: list = field(default_factory=list)


@dataclass
class ValidatedImage:
    data: bytes
    mimetype: str
    width: int
    height: int
    original_format: str
    converted: bool = False

    def is_small(self, min_side=MIN_IMAGE_SIDE):
        return min(self.width, self.height) < min_side


def normalize_code(value):
    """Normaliza referencias: 'M914Y.000.41A 182' -> 'm914y00041a182'."""
    return re.sub(r'[^0-9a-z]', '', (value or '').lower())


def looks_like_search_url(url):
    parsed = urlparse(url or '')
    if _SEARCH_PATH_RE.search(parsed.path or ''):
        return True
    return any(k.lower() in _SEARCH_QUERY_KEYS and v.strip() for k, v in parse_qsl(parsed.query))


# ---------------------------------------------------------------------------
# Análisis HTML
# ---------------------------------------------------------------------------

def _type_names(node):
    raw = node.get('@type')
    types = raw if isinstance(raw, list) else [raw]
    return {str(t).rsplit('/', 1)[-1].rsplit(':', 1)[-1].lower() for t in types if t}


def _walk_jsonld(node, depth=0):
    if depth > 10:
        return
    if isinstance(node, list):
        for item in node:
            yield from _walk_jsonld(item, depth + 1)
    elif isinstance(node, dict):
        yield node
        for key, value in node.items():
            if key not in _JSONLD_SKIP_KEYS and isinstance(value, (list, dict)):
                yield from _walk_jsonld(value, depth + 1)


def _iter_jsonld_nodes(tree):
    for script in tree.xpath('//script[@type="application/ld+json"]'):
        raw = (script.text or '').strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except ValueError:
            try:
                data = json.loads(re.sub(r'[\x00-\x1f]+', ' ', raw))
            except ValueError:
                continue
        yield from _walk_jsonld(data)


def _jsonld_image_urls(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from _jsonld_image_urls(item)
    elif isinstance(value, dict):
        yield from _jsonld_image_urls(value.get('contentUrl') or value.get('url') or '')


def _best_from_srcset(srcset):
    best_url, best_size = None, -1.0
    for entry in re.split(r',\s+', srcset or ''):
        parts = entry.strip().split()
        if not parts:
            continue
        size = 1.0
        if len(parts) > 1:
            match = re.match(r'([\d.]+)[wx]$', parts[1])
            if match:
                size = float(match.group(1))
        if size > best_size:
            best_url, best_size = parts[0], size
    return best_url


def _img_source(img):
    for attr in _IMG_PRIMARY_ATTRS:
        if img.get(attr):
            return img.get(attr)
    for attr in ('data-srcset', 'srcset'):
        best = _best_from_srcset(img.get(attr))
        if best:
            return best
    for attr in _IMG_LAZY_ATTRS:
        value = img.get(attr)
        if value and not value.startswith('data:'):
            return value
    return None


def _img_too_small(img):
    for attr in ('width', 'height'):
        value = (img.get(attr) or '').strip().lower().removesuffix('px')
        if value.isdigit() and int(value) < MIN_IMG_ATTR_SIZE:
            return True
    return False


def _in_gallery(img):
    node = img
    for _depth in range(7):
        if node is None or not isinstance(node.tag, str):
            break
        marker = f"{node.get('class') or ''} {node.get('id') or ''} {node.get('data-role') or ''}"
        if _GALLERY_RE.search(marker) or (node.get('itemprop') or '').lower() == 'image':
            return True
        node = node.getparent()
    return False


def clean_image_url(raw, base_url):
    """Devuelve la URL absoluta de la imagen o None si debe descartarse."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw or raw.startswith(('data:', 'javascript:', 'blob:')):
        return None
    absolute = urljoin(base_url, raw)
    parsed = urlparse(absolute)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        return None
    path = parsed.path.lower()
    if path.endswith(_SKIP_IMAGE_EXT) or _SKIP_IMAGE_RE.search(parsed.path):
        return None
    return absolute


def _meta_values(tree, *names):
    values = []
    for name in names:
        for attr in ('property', 'name'):
            values.extend(tree.xpath(f'//meta[@{attr}=$n]/@content', n=name))
    return [v for v in values if v and v.strip()]


def analyze_page(content, url):
    """Analiza el HTML de una página y devuelve un :class:`PageAnalysis`."""
    analysis = PageAnalysis(url=url)
    if not content:
        return analysis
    try:
        tree = lxml_html.document_fromstring(content)
    except (etree.LxmlError, ValueError):
        return analysis

    base_href = tree.xpath('//base/@href')
    base_url = urljoin(url, base_href[0]) if base_href else url

    title = tree.xpath('string(//title)') or ''
    analysis.title = ' '.join(title.split())
    meta_text = ' '.join(tree.xpath('//meta/@content'))
    alt_text = ' '.join(tree.xpath('//img/@alt'))
    full_text = f'{url} {analysis.title} {meta_text} {alt_text} {tree.text_content()}'
    analysis.text = full_text.lower()
    analysis.norm_text = normalize_code(full_text)
    analysis.og_type = (_meta_values(tree, 'og:type') or [''])[0].strip().lower()

    candidates, seen = [], set()

    def add(raw, origin):
        image_url = clean_image_url(raw, base_url)
        if image_url and image_url not in seen:
            seen.add(image_url)
            candidates.append(ImageCandidate(image_url, origin))

    # 1. Open Graph / Twitter
    og_images = _meta_values(
        tree, 'og:image:secure_url', 'og:image', 'og:image:url', 'twitter:image', 'twitter:image:src')
    for value in og_images:
        add(value, 'og')
    analysis.has_og_image = any(c.origin == 'og' for c in candidates)
    for value in tree.xpath('//link[@rel="image_src"]/@href'):
        add(value, 'og')

    # 2. JSON-LD Product / ImageObject
    product_nodes, image_objects, listing_items = [], [], 0
    for node in _iter_jsonld_nodes(tree):
        types = _type_names(node)
        if types & _PRODUCT_TYPES:
            product_nodes.append(node)
        elif 'imageobject' in types:
            image_objects.append(node)
        if types & {'itemlist', 'offercatalog'}:
            elements = node.get('itemListElement')
            listing_items = max(listing_items, len(elements) if isinstance(elements, list) else 0)
        if 'searchresultspage' in types:
            analysis.is_search_results = True
        if 'collectionpage' in types:
            analysis.is_category = True
    for node in product_nodes:
        for value in _jsonld_image_urls(node.get('image')):
            add(value, 'jsonld')
    for node in image_objects:
        for value in _jsonld_image_urls(node):
            add(value, 'jsonld')

    microdata_product = bool(tree.xpath('//*[contains(@itemtype, "schema.org/Product")]'))
    for value in tree.xpath('//*[@itemprop="image"]/@content | //*[@itemprop="image"]/@href'):
        add(value, 'jsonld')
    analysis.has_product_schema = bool(product_nodes) or microdata_product

    # 3. Galería / 4. Resto de imágenes
    gallery, others = [], []
    for img in tree.xpath('//img'):
        marker = f"{img.get('class') or ''} {img.get('id') or ''} {img.get('alt') or ''}"
        if _img_too_small(img) or _SKIP_IMAGE_RE.search(marker):
            continue
        source = _img_source(img)
        if source:
            (gallery if _in_gallery(img) else others).append(source)
    for value in gallery:
        add(value, 'gallery')
    for value in others:
        add(value, 'img')
    analysis.image_candidates = candidates[:MAX_CANDIDATES]

    # Tipo de página
    product_names = {str(n.get('name') or '').strip().lower() for n in product_nodes}
    is_product_like = analysis.has_product_schema or analysis.og_type.startswith('product')
    if listing_items >= 4 and len(product_nodes) <= 1 and not analysis.og_type.startswith('product'):
        analysis.is_category = True
    if len(product_names) >= 4:
        analysis.is_category = True
    if not is_product_like and _CATEGORY_PATH_RE.search(urlparse(url).path or ''):
        analysis.is_category = True
    h1 = ' '.join(tree.xpath('//h1//text()'))
    if looks_like_search_url(url) or _SEARCH_TITLE_RE.search(f'{analysis.title} {h1}'):
        analysis.is_search_results = True
    return analysis


# ---------------------------------------------------------------------------
# Puntuación
# ---------------------------------------------------------------------------

def _contains_ean(text, ean):
    return bool(re.search(r'(?<!\d)0*' + re.escape(ean) + r'(?!\d)', text))


def score_page(analysis, reference=None, brand=None, eans=()):
    result = ScoreResult()

    norm_ref = normalize_code(reference)
    if len(norm_ref) >= 4 and norm_ref in analysis.norm_text:
        result.reference_found = True
        result.score += SCORE_REFERENCE
        result.reasons.append(f'+{SCORE_REFERENCE} referencia fabricante')

    brand = (brand or '').strip().lower()
    if brand and re.search(r'(?<![0-9a-z])' + re.escape(brand) + r'(?![0-9a-z])', analysis.text):
        result.brand_found = True
        result.score += SCORE_BRAND
        result.reasons.append(f'+{SCORE_BRAND} marca')

    for ean in eans or ():
        digits = re.sub(r'\D', '', ean or '')
        if len(digits) >= 8 and _contains_ean(analysis.text, digits):
            result.ean_found = True
            result.score += SCORE_EAN
            result.reasons.append(f'+{SCORE_EAN} EAN {digits}')
            break

    if analysis.has_product_schema:
        result.score += SCORE_SCHEMA_PRODUCT
        result.reasons.append(f'+{SCORE_SCHEMA_PRODUCT} Schema.org Product')
    if analysis.has_og_image:
        result.score += SCORE_OG_IMAGE
        result.reasons.append(f'+{SCORE_OG_IMAGE} og:image')
    if analysis.is_category:
        result.score += PENALTY_CATEGORY
        result.reasons.append(f'{PENALTY_CATEGORY} página de categoría')
    if analysis.is_search_results:
        result.score += PENALTY_SEARCH_RESULTS
        result.reasons.append(f'{PENALTY_SEARCH_RESULTS} página de resultados')
    return result


# ---------------------------------------------------------------------------
# Validación de imágenes
# ---------------------------------------------------------------------------

def sniff_image_format(data):
    if data[:3] == b'\xff\xd8\xff':
        return 'JPEG'
    if data[:8] == b'\x89PNG\r\n\x1a\n':
        return 'PNG'
    if data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return 'WEBP'
    return None


def looks_like_markup(data):
    head = data[:1024].lstrip(b'\xef\xbb\xbf \t\r\n').lower()
    return head.startswith(b'<') or b'<html' in head or b'<!doctype' in head


def _convert_webp(img):
    out = io.BytesIO()
    has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
    if has_alpha:
        img.convert('RGBA').save(out, format='PNG', optimize=True)
        return out.getvalue(), 'image/png'
    img.convert('RGB').save(out, format='JPEG', quality=90, optimize=True)
    return out.getvalue(), 'image/jpeg'


def validate_image(data, content_type, max_bytes=None):
    """Valida y normaliza una imagen descargada.

    :raises InvalidImageError: si no es una imagen JPG/PNG/WEBP válida.
    """
    ctype = (content_type or '').split(';', 1)[0].strip().lower()
    if ctype.startswith('text/') or any(x in ctype for x in ('html', 'xml', 'json', 'javascript')):
        raise InvalidImageError(f'El Content-Type no es una imagen: {ctype}')
    if ctype not in ALLOWED_CONTENT_TYPES and ctype not in GENERIC_CONTENT_TYPES:
        raise InvalidImageError(f'Tipo de imagen no soportado: {ctype}')
    if not data:
        raise InvalidImageError('Contenido vacío')
    if max_bytes and len(data) > max_bytes:
        raise InvalidImageError(f'La imagen supera el tamaño máximo ({len(data)} bytes)')
    if looks_like_markup(data):
        raise InvalidImageError('El contenido descargado es HTML/XML, no una imagen')
    fmt = sniff_image_format(data)
    if not fmt:
        raise InvalidImageError('Firma binaria no reconocida (se admite JPG, PNG o WEBP)')

    try:
        with Image.open(io.BytesIO(data)) as probe:
            width, height = probe.size
            if width * height > MAX_IMAGE_PIXELS:
                raise InvalidImageError(f'Resolución excesiva ({width}x{height})')
            if probe.format not in MIMETYPE_BY_FORMAT:
                raise InvalidImageError(f'Formato no soportado: {probe.format}')
            probe.verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except InvalidImageError:
        raise
    except Exception as exc:  # PIL lanza excepciones heterogéneas
        raise InvalidImageError(f'Imagen corrupta o ilegible: {exc}') from exc

    try:
        if fmt == 'WEBP':
            out, mimetype = _convert_webp(img)
            return ValidatedImage(out, mimetype, width, height, fmt, converted=True)
        return ValidatedImage(data, MIMETYPE_BY_FORMAT[fmt], width, height, fmt)
    finally:
        img.close()
