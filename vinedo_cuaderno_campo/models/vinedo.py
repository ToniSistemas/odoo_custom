from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError, UserError
import json
import logging
import re
import html
import urllib.request
import urllib.parse

_logger = logging.getLogger(__name__)

_MAPA_BASE = 'https://servicio.mapa.gob.es/regfiweb'
_MAPA_HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; OdooViñedo/1.6)'}

_OPEN_METEO_ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
_OPEN_METEO_FORECAST = 'https://api.open-meteo.com/v1/forecast'


def _grados_a_brujula(deg):
    """Convierte grados (0-360) a punto cardinal de 8 direcciones."""
    if deg is None:
        return False
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SO', 'O', 'NO']
    return dirs[round(float(deg) / 45) % 8]


def _riesgo_automatico(temp_min, viento_max, precipitacion):
    """Determina el riesgo principal a partir de los datos del día."""
    if temp_min is not None and temp_min < 0:
        return 'helada'
    if precipitacion is not None and precipitacion > 20:
        return 'lluvia'
    if viento_max is not None and viento_max > 50:
        return 'viento'
    return 'none'


def _parse_productos_tbody(tbody_html):
    """Parse product rows from a ProductosGrid <tbody> HTML fragment.

    Returns list of dicts: id_mapa, num_registro, nombre, titular, formulado, estado.
    """
    results = []
    _strip = lambda s: re.sub(r'<[^>]+>', '', s).strip()
    for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_html, re.DOTALL):
        btn = re.search(
            r'btnBuscarProductoId[^>]+data-nombre="([^"]*)"[^>]+data-id="(\d+)"', row)
        if not btn:
            continue
        nombre_prod = html.unescape(btn.group(1))
        id_mapa_val = int(btn.group(2))
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
        estado = _strip(cells[0]) if cells else ''
        num_reg = _strip(cells[2]) if len(cells) > 2 else ''
        titular = _strip(cells[4]) if len(cells) > 4 else ''
        formulado_m = re.search(r'class="btnFormulado2"[^>]*>([^<]+)<', row)
        formulado = formulado_m.group(1).strip() if formulado_m else ''
        results.append({
            'id_mapa': id_mapa_val,
            'num_registro': num_reg,
            'nombre': nombre_prod,
            'titular': titular,
            'formulado': formulado,
            'estado': estado,
        })
    return results


def _mapa_buscar_productos(nombre):
    """Searches MAPA fitosanitario registry by commercial name.

    Returns a list of dicts with keys:
    id_mapa, num_registro, nombre, titular, formulado, estado
    """
    url = (_MAPA_BASE + '/Productos/ProductosGrid?NombreComercial='
           + urllib.parse.quote(nombre, safe=''))
    try:
        req = urllib.request.Request(url, headers=_MAPA_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            html_content = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        _logger.warning('MAPA search "%s" failed: %s', nombre, exc)
        return []

    tbody_m = re.search(r'<tbody>(.*?)</tbody>', html_content, re.DOTALL)
    if not tbody_m:
        return []
    return _parse_productos_tbody(tbody_m.group(1))


def _extraer_materia_activa(formulado):
    """Extracts substance name(s) from a Formulado string like 'SUSTANCIA X% [TYPE] P/V'.

    Examples:
      'METALDEHIDO 3% [GB] P/P'          → 'METALDEHIDO'
      'AZOXISTROBIN 25% [SC] P/V'        → 'AZOXISTROBIN'
      'FLORASULAM 0,5% + HALAUXIFEN-METIL 0,6% [OD] P/V' → 'FLORASULAM, HALAUXIFEN-METIL'
    """
    if not formulado:
        return ''
    sustancias = []
    for part in re.split(r'\s*\+\s*', formulado):
        # Remove concentration (digits followed by %, g/, kg/) and everything after
        nombre = re.sub(
            r'\s+\d[\d,.]*\s*(?:g/difusor|g/[a-z]|kg/[a-z]|%).*$',
            '', part.strip(), flags=re.IGNORECASE).strip()
        # Remove formulation type in brackets [EC], [SC], [GB], etc.
        nombre = re.sub(r'\s*\[.*$', '', nombre).strip()
        if nombre and len(nombre) > 1:
            sustancias.append(nombre)
    return ', '.join(sustancias)


def _mapa_importar_todos():
    """Fetchs the complete MAPA fitosanitario catalog via the official JSON export.

    Uses a single HTTP POST to /Exportaciones/ExportJsonProductos (no filters = all
    ~3026 products).  Returns richer data than the HTML grid: observaciones
    (Condicionamiento), fecha_caducidad, and materia_activa derived from Formulado.
    funcion is not available in the bulk export and remains empty until the user
    calls ``action_actualizar_mapa()`` on individual records.
    """
    import json as _json
    from datetime import date as _date

    url = f'{_MAPA_BASE}/Exportaciones/ExportJsonProductos'
    try:
        req = urllib.request.Request(
            url, data=b'',
            headers={**_MAPA_HEADERS, 'Content-Type': 'application/x-www-form-urlencoded'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        _logger.warning('MAPA ExportJsonProductos request failed: %s', exc)
        return []

    try:
        # Response is triple-encoded:
        #   HTTP body  → JSON string  (outer quotes + escaped inner)
        #   json.loads → inner JSON string  {"Contenido": "[...]", "Fecha": "..."}
        #   json.loads → dict with Contenido key whose value is a JSON array string
        #   json.loads → list of product dicts
        data = _json.loads(raw)
        if isinstance(data, str):
            data = _json.loads(data)
        productos_raw = _json.loads(data['Contenido'])
    except Exception as exc:
        _logger.warning('MAPA ExportJsonProductos parse error: %s', exc)
        return []

    results = []
    for p in productos_raw:
        id_mapa = p.get('IdProducto') or 0
        if not id_mapa:
            continue

        # Parse fecha_caducidad from ISO datetime "2026-03-31T00:00:00" → "YYYY-MM-DD" string
        # Keep as string so it is JSON-serializable; Odoo Date fields accept 'YYYY-MM-DD'.
        fecha_cad = False
        str_cad = p.get('FechaCaducidad') or ''
        if len(str_cad) >= 10:
            try:
                # Validate it is a real date before storing
                _date(int(str_cad[:4]), int(str_cad[5:7]), int(str_cad[8:10]))
                fecha_cad = str_cad[:10]
            except Exception:
                pass

        formulado = p.get('Formulado') or ''
        results.append({
            'id_mapa': id_mapa,
            'num_registro': p.get('NumRegistro') or '',
            'nombre': (p.get('Nombre') or '').strip(),
            'titular': p.get('Titular') or '',
            'formulado': formulado,
            'materia_activa': _extraer_materia_activa(formulado),
            'estado': p.get('Estado') or '',
            'observaciones': p.get('Condicionamiento') or '',
            'fecha_caducidad': fecha_cad,
        })

    return results


def _mapa_obtener_funcion(id_mapa):
    """Fetches only the function type from MAPA FuncionesGrid.

    Returns a string like 'Insecticida' or 'Fungicida, Insecticida', empty string
    if MAPA has no function listed, or None on HTTP/parse failure.
    """
    try:
        req = urllib.request.Request(
            f'{_MAPA_BASE}/Productos/FuncionesGrid?IdProducto={id_mapa}',
            headers=_MAPA_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            html_f = r.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        _logger.warning('MAPA FuncionesGrid id=%s failed: %s', id_mapa, exc)
        return None
    funciones = []
    tbody_f = re.search(r'<tbody>(.*?)</tbody>', html_f, re.DOTALL)
    if tbody_f:
        funciones = [
            f.strip() for f in re.findall(r'<td[^>]*>([^<]+)</td>', tbody_f.group(1))
            if f.strip()
        ]
    return ', '.join(funciones)


def _mapa_obtener_detalle(id_mapa):
    """Fetches full product details from MAPA for a given internal id_mapa.

    Makes 3 HTTP calls: GetProductoById, SustanciasGrid, FuncionesGrid.
    Returns a dict suitable for write() on vinedo.fitosanitario, or None on error.
    """
    import json as _json
    from datetime import date as _date

    try:
        req = urllib.request.Request(
            f'{_MAPA_BASE}/Productos/GetProductoById?idProducto={id_mapa}',
            headers=_MAPA_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as r:
            prod = _json.loads(r.read().decode('utf-8'))

        req2 = urllib.request.Request(
            f'{_MAPA_BASE}/Productos/SustanciasGrid?IdProducto={id_mapa}',
            headers=_MAPA_HEADERS)
        with urllib.request.urlopen(req2, timeout=15) as r2:
            html_s = r2.read().decode('utf-8', errors='ignore')

        req3 = urllib.request.Request(
            f'{_MAPA_BASE}/Productos/FuncionesGrid?IdProducto={id_mapa}',
            headers=_MAPA_HEADERS)
        with urllib.request.urlopen(req3, timeout=15) as r3:
            html_f = r3.read().decode('utf-8', errors='ignore')
    except Exception as exc:
        _logger.warning('MAPA detalle id=%s failed: %s', id_mapa, exc)
        return None

    # Parse sustancias (column 1 of each tbody row)
    sustancias = []
    tbody_s = re.search(r'<tbody>(.*?)</tbody>', html_s, re.DOTALL)
    if tbody_s:
        for row in re.findall(r'<tr[^>]*>(.*?)</tr>', tbody_s.group(1), re.DOTALL):
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 2:
                name_s = re.sub(r'<[^>]+>', '', cells[1]).strip()
                if name_s:
                    sustancias.append(name_s)

    # Parse funciones (single column)
    funciones = []
    tbody_f = re.search(r'<tbody>(.*?)</tbody>', html_f, re.DOTALL)
    if tbody_f:
        funciones = [
            f.strip() for f in re.findall(r'<td[^>]*>([^<]+)</td>', tbody_f.group(1))
            if f.strip()
        ]

    # Parse caducidad date format "DD-MM-YYYY"
    fecha_caducidad = False
    str_cad = prod.get('strFechaCaducidad', '') or ''
    if len(str_cad) == 10 and str_cad[2] == '-':
        try:
            fecha_caducidad = _date(int(str_cad[6:]), int(str_cad[3:5]), int(str_cad[:2]))
        except Exception:
            pass

    return {
        'id_mapa': id_mapa,
        'num_registro': prod.get('numRegistro') or '',
        'nombre': (prod.get('nombre') or '').strip(),
        'titular': prod.get('titular') or '',
        'formulado': prod.get('formulado') or '',
        'estado': prod.get('estado') or '',
        'observaciones': prod.get('observaciones') or '',
        'materia_activa': ', '.join(sustancias),
        'funcion': ', '.join(funciones),
        'fecha_caducidad': fecha_caducidad,
        'fecha_consulta': fields.Datetime.now(),
    }


class Territorio(models.Model):
    _name = 'vinedo.territorio'
    _description = 'Territorio/Región'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, index=True)


class Variedad(models.Model):
    _name = 'vinedo.variedad'
    _description = 'Variedad de uva'
    _order = 'name'

    name = fields.Char(string='Variedad', required=True, index=True)
    descripcion = fields.Text(string='Descripción')


class Finca(models.Model):
    _name = 'vinedo.finca'
    _description = 'Finca / Parcela'
    _order = 'name'

    name = fields.Char(string='Nombre', required=True, index=True)
    territory_id = fields.Many2one('vinedo.territorio', string='Territorio', index=True)
    area = fields.Float(string='Extensión (ha)')
    area_m2 = fields.Float(string='Extensión (m²)', compute='_compute_area_m2', digits=(12, 2))
    latitude = fields.Float(string='Latitud', digits=(10, 7), aggregator=False)
    longitude = fields.Float(string='Longitud', digits=(10, 7), aggregator=False)
    ref_sigpac = fields.Char(string='Referencia SIGPAC', index=True, help='Prov-Municipio-Polígono-Parcela-Recinto')
    refs_sigpac_extra = fields.Text(string='Parcelas adicionales SIGPAC', readonly=True,
        help='Referencias SIGPAC de parcelas adicionales, una por línea')
    sigpac_json = fields.Text(string='Datos SIGPAC', readonly=True)
    variedad_ids = fields.One2many('vinedo.plantacion', 'finca_id', string='Variedades plantadas')
    aportacion_ids = fields.One2many('vinedo.aportacion', 'finca_id', string='Aportaciones de minerales')
    tratamiento_ids = fields.One2many('vinedo.tratamiento', 'finca_id', string='Tratamientos')
    trabajo_ids = fields.One2many('vinedo.trabajo', 'finca_id', string='Trabajos')
    recinto_ids = fields.One2many('vinedo.recinto', 'finca_id', string='Recintos SIGPAC')
    recinto_variedad_ids = fields.One2many('vinedo.recinto.variedad', 'finca_id', string='Variedades por recinto')
    plantacion_registro_ids = fields.One2many('vinedo.plantacion.registro', 'finca_id', string='Plantaciones')
    anada_ids = fields.One2many('vinedo.anada', 'finca_id', string='Añadas')
    registro_clima_ids = fields.One2many('vinedo.registro.clima', 'finca_id', string='Climatología')
    seguimiento_fenologico_ids = fields.One2many('vinedo.seguimiento.fenologico', 'finca_id', string='Fenología')
    poda_ids = fields.One2many('vinedo.poda', 'finca_id', string='Podas')

    @api.constrains('latitude', 'longitude')
    def _check_coordinates(self):
        """Validate GPS coordinates range"""
        for rec in self:
            if rec.latitude and not (-90 <= rec.latitude <= 90):
                raise ValidationError(_('Latitud debe estar entre -90 y 90 grados.'))
            if rec.longitude and not (-180 <= rec.longitude <= 180):
                raise ValidationError(_('Longitud debe estar entre -180 y 180 grados.'))

    @api.depends('area')
    def _compute_area_m2(self):
        for rec in self:
            rec.area_m2 = round((rec.area or 0) * 10000, 2)

    def _recompute_area_from_recintos(self):
        """Actualiza el campo area sumando los recintos activos."""
        for rec in self:
            activos = rec.recinto_ids.filtered('activo')
            if activos:
                rec.area = round(sum(activos.mapped('superficie_ha')), 4)

    def _sync_variedades_from_recintos(self):
        """Crea o actualiza vinedo.plantacion agrupando variedades de recintos activos.
        Calcula superficie = superficie_ha del recinto × porcentaje / 100.
        Solo actualiza la superficie; no elimina plantaciones sin recinto."""
        Plantacion = self.env['vinedo.plantacion']
        for finca in self:
            recintos_activos = finca.recinto_ids.filtered('activo')
            # Acumular superficie por variedad aplicando porcentaje de cada recinto.variedad
            sup_por_var = {}
            for recinto in recintos_activos:
                sup_ha = recinto.superficie_ha or 0
                for rv in recinto.variedad_ids:
                    if rv.variedad_id:
                        vid = rv.variedad_id.id
                        share = round(sup_ha * (rv.porcentaje or 0) / 100, 4)
                        sup_por_var[vid] = sup_por_var.get(vid, 0) + share
            # Crear o actualizar plantaciones
            for vid, sup in sup_por_var.items():
                existing = Plantacion.search([
                    ('finca_id', '=', finca.id),
                    ('variedad_id', '=', vid),
                ], limit=1)
                if existing:
                    existing.superficie = round(sup, 4)
                else:
                    Plantacion.create({
                        'finca_id': finca.id,
                        'variedad_id': vid,
                        'superficie': round(sup, 4),
                    })

    def action_consultar_sigpac(self):
        """Consulta la API de SIGPAC para obtener referencia y superficies por uso."""
        self.ensure_one()
        if not self.latitude or not self.longitude:
            raise UserError(_('Introduce la Latitud y Longitud antes de consultar SIGPAC.'))
        import requests
        lat, lon = self.latitude, self.longitude

        # Paso 1: recinto en las coordenadas (sigpac-hubcloud.es)
        url1 = (
            f'https://sigpac-hubcloud.es/servicioconsultassigpac'
            f'/query/recinfobypoint/4326/{float(lon)}/{float(lat)}.json'
        )
        try:
            resp1 = requests.get(url1, timeout=15,
                                 headers={'User-Agent': 'OdooSIGPAC/1.8',
                                          'Accept-Encoding': 'gzip'})
            resp1.raise_for_status()
            arr = resp1.json()
        except Exception as e:
            raise UserError(_('Error al conectar con SIGPAC: %s') % str(e))

        if not isinstance(arr, list) or not arr:
            raise UserError(_(
                'No se encontró ningún recinto SIGPAC en esas coordenadas.\n'
                'Prueba a ajustar ligeramente la posición GPS.'
            ))

        p = arr[0]
        prov    = str(p.get('provincia', ''))
        mun     = str(p.get('municipio', ''))
        agr     = str(p.get('agregado', 0) or 0)
        zona    = str(p.get('zona', 0) or 0)
        pol     = str(p.get('poligono', ''))
        par     = str(p.get('parcela', ''))
        rec_num = str(p.get('recinto', ''))
        uso_principal = p.get('uso_sigpac', '')
        sfc_principal = float(p.get('superficie', 0) or 0) * 10000   # ha → m²
        ref_sigpac = f'{prov}:{mun}:{agr}:{zona}:{pol}:{par}'

        # Paso 2: todos los recintos de la parcela (sigpac-hubcloud.es)
        all_recintos = []
        try:
            url2 = (
                f'https://sigpac-hubcloud.es/servicioconsultassigpac'
                f'/query/recinfoparc/{prov}/{mun}/{agr}/{zona}/{pol}/{par}.json'
            )
            resp2 = requests.get(url2, timeout=15,
                                  headers={'User-Agent': 'OdooSIGPAC/1.8',
                                           'Accept-Encoding': 'gzip'})
            if resp2.status_code == 200:
                arr2 = resp2.json()
                if isinstance(arr2, list):
                    all_recintos = [
                        {
                            'recinto': str(r.get('recinto', '')),
                            'uso': r.get('uso_sigpac', '?'),
                            'superficie': round(float(r.get('superficie', 0) or 0) * 10000, 2),
                        }
                        for r in arr2
                    ]
        except Exception as e:
            _logger.warning('SIGPAC recinfoparc error: %s', e)

        if not all_recintos:
            # Fallback: solo el recinto del punto consultado
            all_recintos = [
                {
                    'recinto': str(r.get('recinto', '')),
                    'uso': r.get('uso_sigpac', '?'),
                    'superficie': round(float(r.get('superficie', 0) or 0) * 10000, 2),
                }
                for r in arr
            ]

        summary = {
            'ref_sigpac': ref_sigpac,
            'provincia': prov,
            'municipio': mun,
            'agregado': agr,
            'zona': zona,
            'poligono': pol,
            'parcela': par,
            'recinto_principal': rec_num,
            'uso_principal': uso_principal,
            'superficie_principal_m2': round(sfc_principal, 2),
            'recintos': all_recintos,
        }
        total_m2 = sum(r['superficie'] for r in all_recintos) or sfc_principal
        recinto_vals = [(5, 0, 0)]
        for r in all_recintos:
            try:
                rnum = int(r['recinto'])
            except (ValueError, TypeError):
                continue
            recinto_vals.append((0, 0, {
                'recinto_num': rnum,
                'uso_sigpac': r['uso'],
                'superficie_ha': round(r['superficie'] / 10000, 4),
                'activo': True,
            }))
        vals = {
            'ref_sigpac': ref_sigpac,
            'refs_sigpac_extra': False,
            'area': round(total_m2 / 10000, 4),
            'sigpac_json': json.dumps(summary, ensure_ascii=False, indent=2),
            'recinto_ids': recinto_vals,
        }
        self.write(vals)

        n_rec = len(all_recintos)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('SIGPAC actualizado'),
                'message': _('Ref: %s | %d recinto(s) | %.0f m²') % (ref_sigpac, n_rec, total_m2),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_abrir_sigpac_visor(self):
        """Abre el visor SIGPAC en una nueva pestaña."""
        self.ensure_one()
        if self.latitude and self.longitude:
            url = f'https://sigpac.mapa.es/fega/visor/#lat={self.latitude}&lng={self.longitude}&zoom=17'
        else:
            url = 'https://sigpac.mapa.es/fega/visor/'
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}


class Plantacion(models.Model):
    _name = 'vinedo.plantacion'
    _description = 'Plantación por variedad en finca'
    _order = 'finca_id, variedad_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True, index=True)
    fecha_plantacion = fields.Date(string='Fecha de plantación')
    superficie = fields.Float(string='Superficie (ha)', digits=(10, 4))
    superficie_m2 = fields.Float(string='Superficie (m²)', compute='_compute_superficie_m2', digits=(12, 2))

    @api.depends('superficie')
    def _compute_superficie_m2(self):
        for rec in self:
            rec.superficie_m2 = round((rec.superficie or 0) * 10000, 2)

    @api.constrains('finca_id', 'variedad_id')
    def _check_unique_finca_variedad(self):
        """Ensure unique combination of finca and variedad"""
        for rec in self:
            if rec.finca_id and rec.variedad_id:
                existing = self.search([
                    ('finca_id', '=', rec.finca_id.id),
                    ('variedad_id', '=', rec.variedad_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_('Ya existe esta variedad en esta finca. Use el registro existente para actualizar datos.'))


class Anada(models.Model):
    _name = 'vinedo.anada'
    _description = 'Lotes de Cosecha'
    _order = 'anio desc, finca_id, variedad_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Nombre', compute='_compute_name', store=True, index=True)
    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, index=True)
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True, index=True)
    anio = fields.Integer(string='Año', required=True, default=lambda self: fields.Date.today().year, aggregator=False)
    graduacion = fields.Float(string='Graduación alcohólica (%vol)', digits=(5, 2), aggregator='avg')
    cantidad = fields.Float(string='Cantidad recolectada (kg)', digits=(12, 2))
    # Campos de cosecha
    fecha_vendimia = fields.Date(string='Fecha de vendimia', index=True)
    cuadrilla = fields.Char(string='Cuadrilla / Responsable')
    rendimiento_kg_ha = fields.Float(string='Rendimiento (kg/ha)', digits=(10, 2), compute='_compute_rendimiento', store=True)
    destino = fields.Selection([
        ('bodega', 'Bodega'),
        ('venta_directa', 'Venta directa'),
        ('autoconsumo', 'Autoconsumo'),
        ('otro', 'Otro'),
    ], string='Destino', default='bodega')
    bodega_destino = fields.Char(string='Bodega / Comprador')
    tiempo_utilizado = fields.Float(string='Tiempo utilizado (h)', digits=(10, 2))
    coste_externo = fields.Float(string='Coste externo (€)', digits=(10, 2))
    coste_maquinaria = fields.Float(string='Coste maquinaria (€)', digits=(10, 2))
    variedad_disponible_ids = fields.Many2many(
        'vinedo.variedad', string='Variedades disponibles',
        compute='_compute_variedad_disponible_ids')

    @api.depends('finca_id')
    def _compute_variedad_disponible_ids(self):
        for rec in self:
            if rec.finca_id:
                rec.variedad_disponible_ids = rec.finca_id.variedad_ids.mapped('variedad_id')
            else:
                rec.variedad_disponible_ids = self.env['vinedo.variedad']

    @api.depends('cantidad')
    def _compute_rendimiento(self):
        for rec in self:
            if rec.cantidad and rec.finca_id and rec.finca_id.area:
                rec.rendimiento_kg_ha = round(rec.cantidad / rec.finca_id.area, 2)
            else:
                rec.rendimiento_kg_ha = 0.0

    @api.depends('finca_id', 'variedad_id', 'anio')
    def _compute_name(self):
        """Auto-generate name from components"""
        for rec in self:
            parts = []
            if rec.anio:
                parts.append(str(rec.anio))
            if rec.finca_id:
                parts.append(rec.finca_id.name)
            if rec.variedad_id:
                parts.append(rec.variedad_id.name)
            rec.name = ' - '.join(parts) if parts else _('Nueva Añada')

    @api.constrains('finca_id', 'variedad_id', 'anio')
    def _check_unique_finca_variedad_anio(self):
        """Ensure unique combination of finca, variedad and year"""
        for rec in self:
            if rec.finca_id and rec.variedad_id and rec.anio:
                existing = self.search([
                    ('finca_id', '=', rec.finca_id.id),
                    ('variedad_id', '=', rec.variedad_id.id),
                    ('anio', '=', rec.anio),
                    ('id', '!=', rec.id)
                ], limit=1)
                if existing:
                    raise ValidationError(_('Ya existe una añada para esta combinación de finca, variedad y año.'))


class Aportacion(models.Model):
    _name = 'vinedo.aportacion'
    _description = 'Aportación de minerales/abonos con coste'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True)
    descripcion = fields.Text(string='Descripción')
    producto_id = fields.Many2one('product.product', string='Producto', required=True, index=True,
        domain=[('categ_id.name', 'ilike', 'mineral'), ('purchase_ok', '=', True)],
        help='Producto de la categoría Minerales. La Referencia Interna puede usarse para identificarlo.')
    cantidad = fields.Float(string='Cantidad (kg)', digits=(10, 2))
    tipo_producto = fields.Selection([
        ('mineral', 'Mineral'),
        ('organico', 'Orgánico'),
    ], string='Tipo', default='mineral')
    precio_kg = fields.Float(string='Precio (€)', digits=(10, 4), aggregator='avg')
    coste = fields.Float(string='Coste (€)', digits=(10, 2), compute='_compute_coste', store=True)

    @api.depends('cantidad', 'precio_kg')
    def _compute_coste(self):
        for rec in self:
            rec.coste = round((rec.cantidad or 0) * (rec.precio_kg or 0), 2)

    @api.onchange('producto_id')
    def _onchange_producto_id(self):
        if self.producto_id:
            self.precio_kg = self.producto_id.standard_price


class Tratamiento(models.Model):
    _name = 'vinedo.tratamiento'
    _description = 'Tratamiento fitosanitario u otro con coste y enlace a Registro MAPA'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    tipo = fields.Selection([('fitosanitario', 'Fitosanitario'), ('otro', 'Otro')],
                           string='Tipo', default='fitosanitario', required=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True, index=True)
    producto = fields.Char(string='Producto')
    dosis = fields.Char(string='Dosis / Observaciones')
    empleado_id = fields.Many2one('hr.employee', string='Empleado', index=True)
    fitosanitario_id = fields.Many2one(
        'vinedo.fitosanitario', string='Ficha Reg. MAPA',
        index=True, ondelete='set null')
    producto_id = fields.Many2one(
        'product.product', string='Producto',
        index=True, ondelete='set null',
        domain=[('categ_id.name', 'ilike', 'fitosanitario'), ('purchase_ok', '=', True)],
        help='Producto de la categoría Fitosanitarios. La Referencia Interna debe ser el Nº de Registro MAPA.')
    litros = fields.Float(string='Litros', digits=(10, 2))
    precio_litro = fields.Float(string='Precio (€)', digits=(10, 4), aggregator='avg')
    coste = fields.Float(string='Coste (€)', digits=(10, 2), compute='_compute_coste', store=True)
    maquinaria_id = fields.Many2one('vinedo.maquinaria', string='Maquinaria', index=True, ondelete='set null')
    materia_activa_info = fields.Char(
        related='fitosanitario_id.materia_activa', string='Materia Activa', readonly=True)
    funcion_info = fields.Char(
        related='fitosanitario_id.funcion', string='Función', readonly=True)
    estado_registro_info = fields.Char(
        related='fitosanitario_id.estado', string='Estado Reg.', readonly=True)
    fecha_caducidad_reg = fields.Date(
        related='fitosanitario_id.fecha_caducidad', string='Cad. Registro', readonly=True)
    observaciones_registro = fields.Text(
        related='fitosanitario_id.observaciones',
        string='Observaciones / Condiciones de Uso', readonly=True)
    phi_info = fields.Integer(
        related='fitosanitario_id.phi_dias', string='PHI (días)', readonly=True)
    phi_vencimiento = fields.Date(
        string='Cosecha no antes de', compute='_compute_phi_vencimiento', store=True,
        help='Fecha más temprana de cosecha permitida tras este tratamiento (fecha aplicación + PHI)')

    @api.depends('litros', 'precio_litro')
    def _compute_coste(self):
        for rec in self:
            rec.coste = round((rec.litros or 0) * (rec.precio_litro or 0), 2)

    @api.depends('fecha', 'fitosanitario_id.phi_dias')
    def _compute_phi_vencimiento(self):
        from datetime import timedelta
        for rec in self:
            phi = rec.fitosanitario_id.phi_dias if rec.fitosanitario_id else 0
            if rec.fecha and phi:
                rec.phi_vencimiento = rec.fecha + timedelta(days=phi)
            else:
                rec.phi_vencimiento = False

    @api.onchange('fitosanitario_id')
    def _onchange_fitosanitario_id(self):
        """When a MAPA record is selected, fill producto and auto-fetch funcion if missing.
        Also tries to auto-link producto_id: first by num_registro=default_code, then by name."""
        if not self.fitosanitario_id:
            return
        self.producto = self.fitosanitario_id.nombre
        # 1. Try by num_registro ↔ default_code (exact)
        prod = None
        num_reg = self.fitosanitario_id.num_registro
        if num_reg:
            prod = self.env['product.product'].search(
                [('default_code', '=', num_reg)], limit=1)
        # 2. Fallback: match by product name (case-insensitive)
        if not prod and self.fitosanitario_id.nombre:
            prod = self.env['product.product'].search(
                [('name', '=ilike', self.fitosanitario_id.nombre)], limit=1)
        if prod:
            self.producto_id = prod
            self.precio_litro = prod.standard_price
        # If funcion not yet populated on the fitosanitario record, fetch it from MAPA now
        fito = self.fitosanitario_id
        if fito.id_mapa and not fito.funcion:
            funcion = _mapa_obtener_funcion(fito.id_mapa)
            if funcion is not None:
                fito.write({'funcion': funcion if funcion else '-'})

    @api.onchange('producto_id')
    def _onchange_producto_id_tratamiento(self):
        """When producto_id is set, fill producto name, precio_litro and try to link fitosanitario_id."""
        if not self.producto_id:
            return
        self.producto = self.producto_id.name
        self.precio_litro = self.producto_id.standard_price
        # Auto-link fitosanitario_id by default_code = num_registro
        if self.producto_id.default_code and not self.fitosanitario_id:
            fito = self.env['vinedo.fitosanitario'].search(
                [('num_registro', '=', self.producto_id.default_code)], limit=1)
            if fito:
                self.fitosanitario_id = fito

    def action_ver_ficha_mapa(self):
        """Opens the official MAPA product page for the linked fitosanitario."""
        self.ensure_one()
        if not self.fitosanitario_id:
            raise UserError(_('Asocia primero este tratamiento a un producto del Registro MAPA.'))
        return self.fitosanitario_id.action_abrir_ficha_mapa()

    def action_buscar_fitosanitario(self):
        """Opens the MAPA search wizard for this tratamiento."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Buscar en Registro MAPA'),
            'res_model': 'vinedo.fitosanitario.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_nombre_busqueda': self.producto or '',
                'default_tratamiento_id': self.id,
            },
        }


class Poda(models.Model):
    _name = 'vinedo.poda'
    _description = 'Registro de podas'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True, index=True)
    tipo_poda = fields.Selection([('invierno', 'Poda de invierno'), ('verde', 'Poda en verde')],
                                 string='Tipo de poda')
    descripcion = fields.Text(string='Descripción')
    empleado_id = fields.Many2one('hr.employee', string='Empleado', index=True)


class Maquinaria(models.Model):
    _name = 'vinedo.maquinaria'
    _description = 'Maquinaria agrícola con titular (contacto) y fecha de compra'
    _order = 'name'

    name = fields.Char(string='Nombre / Descripción', required=True, index=True)
    titular_id = fields.Many2one('res.partner', string='Titular', index=True)
    fecha_compra = fields.Date(string='Fecha de compra')
    tipo = fields.Selection([
        ('tractor', 'Tractor'),
        ('atomizador', 'Atomizador'),
        ('pulverizador', 'Pulverizador'),
        ('cisterna', 'Cisterna'),
        ('remolque', 'Remolque'),
        ('vendimadora', 'Vendimadora'),
        ('desbrozadora', 'Desbrozadora'),
        ('otro', 'Otro'),
    ], string='Tipo', required=True, default='otro')
    registro = fields.Char(string='Registro / Matrícula')


class TipoTrabajo(models.Model):
    _name = 'vinedo.tipo.trabajo'
    _description = 'Tipo de trabajo en viñedo'
    _order = 'name'

    name = fields.Char(string='Tipo de trabajo', required=True)

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Ya existe un tipo de trabajo con ese nombre.'),
    ]


class Trabajo(models.Model):
    _name = 'vinedo.trabajo'
    _description = 'Trabajo realizado en finca'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', default=fields.Date.today, required=True, index=True)
    empleado_id = fields.Many2one('hr.employee', string='Empleado', index=True)
    tipo_trabajo = fields.Many2one('vinedo.tipo.trabajo', string='Trabajo realizado', required=True)
    horas = fields.Float(string='Horas', digits=(5, 2))
    observaciones = fields.Text(string='Observaciones')


class RecintoVariedad(models.Model):
    """Distribución de variedades dentro de un recinto SIGPAC mediante porcentaje."""
    _name = 'vinedo.recinto.variedad'
    _description = 'Variedad por recinto SIGPAC'
    _order = 'recinto_id, variedad_id'

    recinto_id = fields.Many2one('vinedo.recinto', string='Recinto', required=True, ondelete='cascade', index=True)
    finca_id = fields.Many2one('vinedo.finca', string='Finca', related='recinto_id.finca_id', store=True, index=True, readonly=True)
    variedad_id = fields.Many2one('vinedo.variedad', string='Variedad', required=True)
    porcentaje = fields.Float(string='Porcentaje (%)', digits=(5, 2), default=100.0)
    superficie_ha = fields.Float(string='Superficie (ha)', compute='_compute_superficie', digits=(10, 4), store=True)
    superficie_m2 = fields.Float(string='Superficie (m²)', compute='_compute_superficie', digits=(12, 2), store=True)

    @api.depends('recinto_id.superficie_ha', 'porcentaje')
    def _compute_superficie(self):
        for rec in self:
            sup_ha = round((rec.recinto_id.superficie_ha or 0) * (rec.porcentaje or 0) / 100, 4)
            rec.superficie_ha = sup_ha
            rec.superficie_m2 = round(sup_ha * 10000, 2)

    @api.constrains('porcentaje')
    def _check_porcentaje(self):
        for rec in self:
            if rec.porcentaje <= 0 or rec.porcentaje > 100:
                raise ValidationError(_('El porcentaje debe estar entre 0.01 y 100.'))

    def write(self, vals):
        result = super().write(vals)
        fincas = self.mapped('finca_id')
        if fincas:
            fincas._sync_variedades_from_recintos()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('finca_id')._sync_variedades_from_recintos()
        return records

    def unlink(self):
        fincas = self.mapped('finca_id')
        result = super().unlink()
        if fincas:
            fincas._sync_variedades_from_recintos()
        return result


class Recinto(models.Model):
    _name = 'vinedo.recinto'
    _description = 'Recinto SIGPAC de una finca'
    _order = 'recinto_num'
    _rec_name = 'name'

    _sql_constraints = [
        ('finca_recinto_num_uniq', 'unique(finca_id, recinto_num)',
         'Ya existe un recinto con ese número en esta finca.'),
    ]

    name = fields.Char(string='Nº Recinto', compute='_compute_name', store=True)
    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    recinto_num = fields.Integer(string='Recinto', required=True)
    uso_sigpac = fields.Char(string='Uso SIGPAC')
    superficie_ha = fields.Float(string='Superficie (ha)', digits=(10, 4))
    superficie_m2 = fields.Float(string='Superficie (m²)', compute='_compute_superficie_m2', digits=(12, 2))
    activo = fields.Boolean(string='Incluir', default=True)
    variedad_ids = fields.One2many('vinedo.recinto.variedad', 'recinto_id', string='Variedades')
    variedad_resumen = fields.Char(string='Variedades', compute='_compute_variedad_resumen')

    @api.depends('superficie_ha')
    def _compute_superficie_m2(self):
        for rec in self:
            rec.superficie_m2 = round((rec.superficie_ha or 0) * 10000, 2)

    @api.depends('recinto_num')
    def _compute_name(self):
        for rec in self:
            rec.name = str(rec.recinto_num) if rec.recinto_num else ''

    def _compute_variedad_resumen(self):
        for rec in self:
            parts = []
            for rv in rec.variedad_ids:
                if rv.variedad_id:
                    pct = rv.porcentaje
                    pct_str = f'{pct:.0f}%' if pct == int(pct) else f'{pct:.1f}%'
                    parts.append(f'{rv.variedad_id.name} {pct_str}')
            rec.variedad_resumen = ', '.join(parts) if parts else ''

    def write(self, vals):
        result = super().write(vals)
        if 'activo' in vals or 'superficie_ha' in vals:
            self.mapped('finca_id')._recompute_area_from_recintos()
        if 'activo' in vals or 'superficie_ha' in vals:
            self.mapped('finca_id')._sync_variedades_from_recintos()
        return result

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.mapped('finca_id')._recompute_area_from_recintos()
        records.mapped('finca_id')._sync_variedades_from_recintos()
        return records

    def action_toggle_activo(self):
        for rec in self:
            rec.activo = not rec.activo


class RegistroClima(models.Model):
    """Registro meteorológico diario por finca."""
    _name = 'vinedo.registro.clima'
    _description = 'Registro meteorológico'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', required=True, index=True)
    temperatura_max = fields.Float(string='Temp. máxima (°C)', digits=(5, 1), aggregator='max')
    temperatura_min = fields.Float(string='Temp. mínima (°C)', digits=(5, 1), aggregator='min')
    temperatura_media = fields.Float(string='Temp. media (°C)', digits=(5, 1), aggregator='avg')
    precipitacion = fields.Float(string='Precipitación (mm)', digits=(6, 1), aggregator='sum')
    humedad_relativa = fields.Float(string='Humedad relativa (%)', digits=(5, 1), aggregator=False)
    viento_velocidad = fields.Float(string='Viento (km/h)', digits=(5, 1), aggregator=False)
    viento_direccion = fields.Selection([
        ('N', 'N'), ('NE', 'NE'), ('E', 'E'), ('SE', 'SE'),
        ('S', 'S'), ('SO', 'SO'), ('O', 'O'), ('NO', 'NO'),
    ], string='Dirección viento')
    riesgo = fields.Selection([
        ('helada', 'Helada'),
        ('pedrisco', 'Pedrisco / Granizo'),
        ('incendio', 'Incendio'),
        ('viento', 'Viento fuerte'),
        ('lluvia', 'Lluvia intensa'),
        ('none', 'Sin riesgos'),
    ], string='Riesgo detectado', default='none')
    observaciones = fields.Text(string='Observaciones')

    _sql_constraints = [
        ('finca_fecha_uniq', 'unique(finca_id, fecha)',
         'Ya existe un registro climático para esta fecha en esta finca.'),
    ]


class SeguimientoFenologico(models.Model):
    """Seguimiento fenológico BBCH de la vid."""
    _name = 'vinedo.seguimiento.fenologico'
    _description = 'Seguimiento fenológico BBCH'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha', required=True, index=True)
    codigo_bbch = fields.Selection([
        ('00', '00 - Reposo invernal (yemas)'),
        ('01', '01 - Hinchazón de la yema'),
        ('03', '03 - Punta verde'),
        ('07', '07 - Punta algodonosa / Pámpano visible'),
        ('09', '09 - Brotación / Yema abierta'),
        ('11', '11 - Primera hoja desplegada'),
        ('13', '13 - Tercera hoja desplegada'),
        ('15', '15 - Quinta hoja desplegada'),
        ('19', '19 - Nueve o más hojas desplegadas'),
        ('53', '53 - Inflorescencia visible'),
        ('55', '55 - Inflorescencia desarrollada / Botones florales separados'),
        ('57', '57 - Inicio de floración'),
        ('61', '61 - Plena floración (10-30% caída de capuchones)'),
        ('65', '65 - Floración (80% caída de capuchones)'),
        ('68', '68 - Final de floración / Cuajado'),
        ('71', '71 - Cuajado / Frutos visibles'),
        ('73', '73 - Racimos colgantes / Bayas tamaño pimienta'),
        ('75', '75 - Bayas tamaño guisante / Cierre del racimo'),
        ('77', '77 - Inicio de envero'),
        ('79', '79 - Pleno envero'),
        ('81', '81 - Maduración / Bayas coloreadas'),
        ('83', '83 - Maduración avanzada'),
        ('85', '85 - Madurez tecnológica'),
        ('89', '89 - Madurez completa / Recolección'),
        ('91', '91 - Inicio de senescencia'),
        ('97', '97 - Fin del ciclo / Caída de hoja'),
    ], string='Código BBCH', required=True)
    descripcion = fields.Char(string='Descripción', compute='_compute_descripcion')
    observaciones = fields.Text(string='Observaciones')

    @api.depends('codigo_bbch')
    def _compute_descripcion(self):
        for rec in self:
            rec.descripcion = dict(rec._fields['codigo_bbch'].selection).get(rec.codigo_bbch, '')


class PlantacionRegistro(models.Model):
    """Registro de plantaciones y arranques en una finca."""
    _name = 'vinedo.plantacion.registro'
    _description = 'Registro de plantación / arranque'
    _order = 'fecha desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', required=True, ondelete='cascade', index=True)
    fecha = fields.Date(string='Fecha de plantación', default=fields.Date.today, required=True)
    num_plantas = fields.Integer(string='Nº de plantas')
    tipo = fields.Selection([
        ('plantado', 'Plantado'),
        ('arrancado', 'Arrancado'),
    ], string='Plantado/Arrancado', required=True, default='plantado')


class Fitosanitario(models.Model):
    """Catálogo de productos fitosanitarios del Registro MAPA.

    Los datos se pueden poblar automáticamente mediante la consulta al
    Registro de Productos Fitosanitarios del MAPA (servicio.mapa.gob.es/regfiweb).
    """
    _name = 'vinedo.fitosanitario'
    _description = 'Producto Fitosanitario (Registro MAPA)'
    _rec_name = 'nombre'
    _order = 'nombre'

    id_mapa = fields.Integer(string='ID interno MAPA', readonly=True, index=True)
    num_registro = fields.Char(string='Nº Registro', index=True)
    nombre = fields.Char(string='Nombre Comercial', required=True, index=True)
    titular = fields.Char(string='Titular')
    formulado = fields.Char(string='Formulado')
    funcion = fields.Char(string='Función (tipo)')
    materia_activa = fields.Char(string='Materia(s) Activa(s)')
    estado = fields.Char(string='Estado')
    fecha_caducidad = fields.Date(string='Caducidad Registro')
    observaciones = fields.Text(string='Observaciones / Condiciones de Uso')
    phi_dias = fields.Integer(
        string='Plazo de Seguridad / PHI (días)',
        help='Número mínimo de días entre la última aplicación del producto y la cosecha (Pre-Harvest Interval)')
    fecha_consulta = fields.Datetime(string='Última consulta MAPA', readonly=True)

    def action_actualizar_mapa(self):
        """Re-fetches data from MAPA using id_mapa already stored."""
        for rec in self:
            if not rec.id_mapa:
                raise UserError(_(
                    'Este registro no tiene un ID MAPA asignado. '
                    'Usa la búsqueda para encontrarlo primero.'))
            data = _mapa_obtener_detalle(rec.id_mapa)
            if data is None:
                raise UserError(_(
                    'No se pudo obtener información de MAPA para el producto "%s". '
                    'Comprueba la conexión a internet e inténtalo de nuevo.') % rec.nombre)
            rec.write(data)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('MAPA actualizado'),
                'message': _('Datos actualizados desde el Registro de Productos Fitosanitarios.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_abrir_ficha_mapa(self):
        """Opens the official MAPA product page in a new browser tab."""
        self.ensure_one()
        if not self.num_registro:
            raise UserError(_('Sin número de registro no se puede abrir la ficha del MAPA.'))
        return {
            'type': 'ir.actions.act_url',
            'url': (f'https://servicio.mapa.gob.es/regfiweb/#'
                    f'?numreg={urllib.parse.quote(self.num_registro)}'),
            'target': 'new',
        }

    def action_completar_funciones(self):
        """Fetches funcion from MAPA for up to 200 products at a time where it is still missing.

        Products with no function in MAPA are stored as '-' to avoid re-querying them.
        Run repeatedly until the notification says '¡Completado!'.
        """
        pendientes = self.env['vinedo.fitosanitario'].search(
            [('id_mapa', '!=', 0), ('funcion', '=', False)],
            limit=200,
            order='id',
        )
        if not pendientes:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Completar funciones MAPA'),
                    'message': _('Todos los productos ya tienen función asignada.'),
                    'type': 'success',
                    'sticky': False,
                },
            }

        actualizados = errores = 0
        for rec in pendientes:
            funcion = _mapa_obtener_funcion(rec.id_mapa)
            if funcion is None:
                errores += 1
                continue
            try:
                with self.env.cr.savepoint():
                    # Store '-' when MAPA has no function listed, to avoid re-querying
                    rec.write({'funcion': funcion if funcion else '-'})
                    self.env.flush_all()
                actualizados += 1
            except Exception as exc:
                self.env.invalidate_all()
                _logger.warning('MAPA funcion: error writing rec %s: %s', rec.id, exc)
                errores += 1

        quedan = self.env['vinedo.fitosanitario'].search_count(
            [('id_mapa', '!=', 0), ('funcion', '=', False)]
        )
        if quedan:
            msg = _(
                '%d funciones actualizadas, %d errores. '
                'Quedan %d sin función — vuelve a ejecutar.'
            ) % (actualizados, errores, quedan)
        else:
            msg = _('%d funciones actualizadas. ¡Completado!') % actualizados

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Completar funciones MAPA'),
                'message': msg,
                'type': 'warning' if quedan else 'success',
                'sticky': True,
            },
        }

    def action_importar_catalogo_mapa(self):
        """Opens the two-step import wizard."""
        return self.env['vinedo.fitosanitario.import.wizard'].action_open()


class FitosanitarioWizard(models.TransientModel):
    """Wizard to search the MAPA phytosanitary registry and link a product to a Tratamiento."""
    _name = 'vinedo.fitosanitario.wizard'
    _description = 'Buscar Producto Fitosanitario (MAPA)'

    nombre_busqueda = fields.Char(string='Nombre del producto', required=True)
    linea_ids = fields.One2many(
        'vinedo.fitosanitario.wizard.linea', 'wizard_id', string='Resultados')
    tratamiento_id = fields.Many2one('vinedo.tratamiento', string='Tratamiento')

    def action_buscar(self):
        """Calls MAPA API and populates linea_ids with results."""
        self.linea_ids.unlink()
        resultados = _mapa_buscar_productos(self.nombre_busqueda)
        if not resultados:
            raise UserError(_(
                'No se encontraron productos con el nombre "%s" en el Registro MAPA.\n'
                'Prueba con otro nombre o parte del nombre.') % self.nombre_busqueda)
        for r in resultados:
            r['wizard_id'] = self.id
            self.env['vinedo.fitosanitario.wizard.linea'].create(r)
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class FitosanitarioWizardLinea(models.TransientModel):
    """Result line for the MAPA search wizard."""
    _name = 'vinedo.fitosanitario.wizard.linea'
    _description = 'Resultado búsqueda MAPA'

    wizard_id = fields.Many2one(
        'vinedo.fitosanitario.wizard', string='Wizard', ondelete='cascade')
    id_mapa = fields.Integer(string='ID MAPA')
    num_registro = fields.Char(string='Nº Registro')
    nombre = fields.Char(string='Nombre Comercial')
    titular = fields.Char(string='Titular')
    formulado = fields.Char(string='Formulado')
    estado = fields.Char(string='Estado')

    def action_seleccionar(self):
        """Fetches full MAPA details, creates/updates the fitosanitario record,
        and links it to the tratamiento if set."""
        self.ensure_one()
        data = _mapa_obtener_detalle(self.id_mapa)
        if data is None:
            raise UserError(_(
                'No se pudieron obtener los datos del MAPA para "%s".\n'
                'Comprueba la conexión a internet e inténtalo de nuevo.') % self.nombre)

        Fitosanitario = self.env['vinedo.fitosanitario']
        fitosanitario = Fitosanitario.search(
            [('id_mapa', '=', self.id_mapa)], limit=1)
        if fitosanitario:
            fitosanitario.write(data)
        else:
            fitosanitario = Fitosanitario.create(data)

        wizard = self.wizard_id
        if wizard.tratamiento_id and wizard.tratamiento_id.id:
            vals = {'fitosanitario_id': fitosanitario.id}
            if not wizard.tratamiento_id.producto:
                vals['producto'] = fitosanitario.nombre
            wizard.tratamiento_id.write(vals)

        return {'type': 'ir.actions.act_window_close'}


class FitosanitarioImportWizard(models.TransientModel):
    """Two-step wizard: fetch MAPA catalog → confirm count → import with savepoints."""
    _name = 'vinedo.fitosanitario.import.wizard'
    _description = 'Descargar catálogo MAPA'

    fase = fields.Selection([
        ('inicio', 'Listo para buscar'),
        ('confirmar', 'Confirmar importación'),
        ('listo', 'Completado'),
    ], default='inicio', readonly=True)
    total_mapa = fields.Integer(string='Productos encontrados en MAPA', readonly=True)
    total_creados = fields.Integer(string='Nuevos creados', readonly=True)
    total_actualizados = fields.Integer(string='Actualizados', readonly=True)
    total_errores = fields.Integer(string='Con errores', readonly=True)
    productos_json = fields.Text()  # internal, not shown

    @api.model
    def action_open(self):
        """Creates a fresh wizard instance and opens it."""
        wiz = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': _('Descargar catálogo MAPA'),
            'res_model': self._name,
            'res_id': wiz.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_buscar(self):
        """Phase 1: Fetch product list from MAPA (HTTP only, no DB writes)."""
        self.ensure_one()
        productos = _mapa_importar_todos()
        self.write({
            'fase': 'confirmar',
            'total_mapa': len(productos),
            'productos_json': json.dumps(productos, ensure_ascii=False),
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_importar(self):
        """Phase 2: Write fetched products to DB.

        New products are created in a single batch call; existing ones are updated
        per-record with savepoints so a concurrent-update error never kills the import.
        """
        self.ensure_one()
        productos = json.loads(self.productos_json or '[]')
        Fito = self.env['vinedo.fitosanitario']
        creados = actualizados = errores = 0

        # Index existing records by id_mapa for O(1) lookup instead of N queries
        ids_mapa = [p['id_mapa'] for p in productos if p.get('id_mapa')]
        existentes = {r.id_mapa: r for r in Fito.search([('id_mapa', 'in', ids_mapa)])}

        nuevos = []
        for p in productos:
            if not p.get('id_mapa'):
                continue
            existing = existentes.get(p['id_mapa'])
            if existing:
                try:
                    with self.env.cr.savepoint():
                        existing.write({
                            'num_registro': p['num_registro'],
                            'nombre': p['nombre'],
                            'titular': p['titular'],
                            'formulado': p['formulado'],
                            'materia_activa': p.get('materia_activa', ''),
                            'estado': p['estado'],
                            'observaciones': p.get('observaciones', ''),
                            'fecha_caducidad': p.get('fecha_caducidad', False),
                        })
                    actualizados += 1
                except Exception as exc:
                    self.env.invalidate_all()
                    _logger.warning(
                        'MAPA import: skipping update "%s" (id_mapa=%s): %s',
                        p.get('nombre', '?'), p.get('id_mapa'), exc)
                    errores += 1
            else:
                nuevos.append(p)

        # Batch-create all new records in one call
        if nuevos:
            try:
                Fito.create(nuevos)
                creados = len(nuevos)
            except Exception as exc:
                _logger.warning('MAPA import: batch create failed (%s), retrying one-by-one', exc)
                for p in nuevos:
                    try:
                        with self.env.cr.savepoint():
                            Fito.create(p)
                        creados += 1
                    except Exception as exc2:
                        self.env.invalidate_all()
                        _logger.warning(
                            'MAPA import: skipping create "%s" (id_mapa=%s): %s',
                            p.get('nombre', '?'), p.get('id_mapa'), exc2)
                        errores += 1

        self.write({
            'fase': 'listo',
            'total_creados': creados,
            'total_actualizados': actualizados,
            'total_errores': errores,
            'productos_json': False,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }


class EstadisticaGasto(models.Model):
    """Vista SQL unificada de costes (tratamientos, aportaciones) y horas (trabajos) por finca."""
    _name = 'vinedo.estadistica.gasto'
    _description = 'Estadística de gastos y horas por finca'
    _auto = False
    _rec_name = 'tipo'
    _order = 'fecha desc'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', readonly=True)
    fecha = fields.Date(string='Fecha', readonly=True)
    tipo = fields.Selection([
        ('tratamiento', 'Tratamiento'),
        ('aportacion', 'Aportación'),
        ('trabajo', 'Trabajo'),
    ], string='Tipo', readonly=True)
    empleado_id = fields.Many2one('hr.employee', string='Empleado', readonly=True)
    producto_id = fields.Many2one('product.product', string='Producto', readonly=True)
    tipo_trabajo_id = fields.Many2one('vinedo.tipo.trabajo', string='Tipo de trabajo', readonly=True)
    coste = fields.Float(string='Coste (€)', digits=(10, 2), readonly=True)
    horas = fields.Float(string='Horas', digits=(5, 2), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW vinedo_estadistica_gasto AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY sub.fecha DESC, sub.finca_id) AS id,
                    sub.finca_id,
                    sub.fecha,
                    sub.tipo,
                    sub.empleado_id,
                    sub.producto_id,
                    sub.tipo_trabajo_id,
                    sub.coste,
                    sub.horas
                FROM (
                    SELECT
                        t.finca_id,
                        t.fecha,
                        'tratamiento'::varchar AS tipo,
                        t.empleado_id,
                        t.producto_id,
                        NULL::integer AS tipo_trabajo_id,
                        t.coste,
                        0.0::double precision AS horas
                    FROM vinedo_tratamiento t
                    UNION ALL
                    SELECT
                        a.finca_id,
                        a.fecha,
                        'aportacion'::varchar AS tipo,
                        NULL::integer AS empleado_id,
                        a.producto_id,
                        NULL::integer AS tipo_trabajo_id,
                        a.coste,
                        0.0::double precision AS horas
                    FROM vinedo_aportacion a
                    UNION ALL
                    SELECT
                        tr.finca_id,
                        tr.fecha,
                        'trabajo'::varchar AS tipo,
                        tr.empleado_id,
                        NULL::integer AS producto_id,
                        tr.tipo_trabajo AS tipo_trabajo_id,
                        0.0::double precision AS coste,
                        tr.horas
                    FROM vinedo_trabajo tr
                ) sub
            )
        """)


class ResumenAnada(models.Model):
    """Vista SQL agregada: costes totales y coste/kg por finca y año de añada."""
    _name = 'vinedo.resumen.anada'
    _description = 'Coste por añada (resumen finca / año)'
    _auto = False
    _rec_name = 'finca_id'
    _order = 'anio desc, finca_id'

    finca_id = fields.Many2one('vinedo.finca', string='Finca', readonly=True)
    anio = fields.Integer(string='Año', readonly=True)
    coste_tratamientos = fields.Float(string='Tratamientos (€)', digits=(10, 2), readonly=True)
    coste_aportaciones = fields.Float(string='Aportaciones (€)', digits=(10, 2), readonly=True)
    coste_total = fields.Float(string='Coste total (€)', digits=(10, 2), readonly=True)
    horas_total = fields.Float(string='Horas trabajadas', digits=(8, 2), readonly=True)
    cantidad_kg = fields.Float(string='Kg cosechados', digits=(12, 2), readonly=True)
    coste_por_kg = fields.Float(string='Coste/kg (€)', digits=(10, 4), readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW vinedo_resumen_anada AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY sub.anio DESC, sub.finca_id) AS id,
                    sub.finca_id,
                    sub.anio,
                    sub.coste_tratamientos,
                    sub.coste_aportaciones,
                    sub.coste_total,
                    sub.horas_total,
                    COALESCE(kg.cantidad_total, 0.0) AS cantidad_kg,
                    CASE WHEN COALESCE(kg.cantidad_total, 0.0) > 0
                         THEN ROUND((sub.coste_total / kg.cantidad_total)::numeric, 4)
                         ELSE 0.0
                    END AS coste_por_kg
                FROM (
                    SELECT
                        finca_id,
                        EXTRACT(YEAR FROM fecha)::integer AS anio,
                        SUM(CASE WHEN tipo = 'tratamiento' THEN coste ELSE 0 END) AS coste_tratamientos,
                        SUM(CASE WHEN tipo = 'aportacion'  THEN coste ELSE 0 END) AS coste_aportaciones,
                        SUM(coste)  AS coste_total,
                        SUM(horas)  AS horas_total
                    FROM (
                        SELECT finca_id, fecha, 'tratamiento' AS tipo, coste, 0.0::double precision AS horas
                            FROM vinedo_tratamiento
                        UNION ALL
                        SELECT finca_id, fecha, 'aportacion' AS tipo, coste, 0.0::double precision AS horas
                            FROM vinedo_aportacion
                        UNION ALL
                        SELECT finca_id, fecha, 'trabajo' AS tipo, 0.0::double precision AS coste, horas
                            FROM vinedo_trabajo
                    ) movs
                    GROUP BY finca_id, EXTRACT(YEAR FROM fecha)::integer
                ) sub
                LEFT JOIN (
                    SELECT finca_id, anio, SUM(cantidad) AS cantidad_total
                        FROM vinedo_anada
                        GROUP BY finca_id, anio
                ) kg ON kg.finca_id = sub.finca_id AND kg.anio = sub.anio
            )
        """)


class ClimaImportWizard(models.TransientModel):
    """Wizard para importar datos meteorologicos diarios desde Open-Meteo API."""
    _name = 'vinedo.clima.import.wizard'
    _description = 'Importar datos Open-Meteo'

    finca_id = fields.Many2one(
        'vinedo.finca', string='Finca',
        help='La finca debe tener coordenadas GPS (latitud y longitud).')
    fecha_inicio = fields.Date(
        string='Fecha inicio',
        default=lambda self: fields.Date.today().replace(month=1, day=1))
    fecha_fin = fields.Date(
        string='Fecha fin',
        default=fields.Date.today)
    sobrescribir = fields.Boolean(
        string='Sobrescribir registros existentes', default=False,
        help='Si esta marcado, los registros ya existentes se actualizan con los nuevos datos.')
    resultado = fields.Char(string='Resultado', readonly=True)

    @api.model
    def action_open(self):
        """Abre el formulario del wizard sin pre-crear el registro."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar datos meteorologicos'),
            'res_model': self._name,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_importar(self):
        """Descarga datos de Open-Meteo y crea/actualiza registros de clima."""
        import datetime
        self.ensure_one()
        if not self.finca_id:
            raise UserError(_('Selecciona una finca antes de importar.'))
        if not self.fecha_inicio or not self.fecha_fin:
            raise UserError(_('Introduce el rango de fechas antes de importar.'))
        finca = self.finca_id
        if not finca.latitude or not finca.longitude:
            raise UserError(_(
                'La finca "%s" no tiene coordenadas GPS.\n'
                'Introduce la latitud y longitud en la ficha de la finca antes de importar.'
            ) % finca.name)

        today = datetime.date.today()
        archive_cutoff = today - datetime.timedelta(days=7)
        weather = {}

        if self.fecha_inicio <= archive_cutoff:
            end_arch = min(self.fecha_fin, archive_cutoff)
            weather.update(self._llamar_open_meteo(
                finca.latitude, finca.longitude,
                str(self.fecha_inicio), str(end_arch),
                _OPEN_METEO_ARCHIVE))

        if self.fecha_fin > archive_cutoff:
            start_fc = max(self.fecha_inicio, archive_cutoff + datetime.timedelta(days=1))
            weather.update(self._llamar_open_meteo(
                finca.latitude, finca.longitude,
                str(start_fc), str(self.fecha_fin),
                _OPEN_METEO_FORECAST))

        if not weather:
            raise UserError(_(
                'Open-Meteo no devolvio datos para el periodo solicitado. '
                'Verifica las fechas y las coordenadas de la finca.'))

        Clima = self.env['vinedo.registro.clima']
        creados = actualizados = 0

        for fecha_str, vals in sorted(weather.items()):
            vals['finca_id'] = finca.id
            vals['fecha'] = fecha_str
            existing = Clima.search([
                ('finca_id', '=', finca.id),
                ('fecha', '=', fecha_str),
            ], limit=1)
            if existing:
                if self.sobrescribir:
                    existing.write(vals)
                    actualizados += 1
            else:
                Clima.create(vals)
                creados += 1

        msg = _('Importacion completada: %d registros creados, %d actualizados.') % (
            creados, actualizados)
        self.write({'resultado': msg})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _llamar_open_meteo(self, lat, lon, fecha_ini, fecha_fin_str, base_url):
        """Llama al endpoint de Open-Meteo y devuelve dict {fecha_str: vals_dict}."""
        params = urllib.parse.urlencode({
            'latitude': lat,
            'longitude': lon,
            'start_date': fecha_ini,
            'end_date': fecha_fin_str,
            'daily': ','.join([
                'temperature_2m_max',
                'temperature_2m_min',
                'temperature_2m_mean',
                'precipitation_sum',
                'wind_speed_10m_max',
                'wind_direction_10m_dominant',
            ]),
            'hourly': 'relative_humidity_2m',
            'timezone': 'Europe/Madrid',
            'wind_speed_unit': 'kmh',
        })
        url = '%s?%s' % (base_url, params)
        _logger.info('Open-Meteo request: %s', url)
        try:
            req = urllib.request.Request(
                url, headers={'User-Agent': 'OdooVinedoCuadernoCampo/2.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode('utf-8'))
        except Exception as exc:
            raise UserError(_('Error al conectar con Open-Meteo: %s') % str(exc))

        if data.get('error'):
            raise UserError(_('Open-Meteo: %s') % data.get('reason', 'Error desconocido'))

        # Calcular humedad media diaria desde datos horarios
        humidity_daily = {}
        if 'hourly' in data:
            times_h = data['hourly'].get('time', [])
            hums = data['hourly'].get('relative_humidity_2m', [])
            acc = {}
            for t, h in zip(times_h, hums):
                day = t[:10]
                if h is not None:
                    acc.setdefault(day, []).append(h)
            for day, vals_list in acc.items():
                humidity_daily[day] = round(sum(vals_list) / len(vals_list), 1)

        daily = data.get('daily', {})
        dates = daily.get('time', [])

        def _v(key, idx):
            lst = daily.get(key, [])
            return lst[idx] if idx < len(lst) else None

        results = {}
        for i, fecha_str in enumerate(dates):
            temp_min = _v('temperature_2m_min', i)
            viento_max = _v('wind_speed_10m_max', i)
            precip = _v('precipitation_sum', i)
            results[fecha_str] = {
                'temperatura_max': _v('temperature_2m_max', i) or 0.0,
                'temperatura_min': temp_min or 0.0,
                'temperatura_media': _v('temperature_2m_mean', i) or 0.0,
                'precipitacion': precip or 0.0,
                'viento_velocidad': viento_max or 0.0,
                'viento_direccion': _grados_a_brujula(_v('wind_direction_10m_dominant', i)),
                'humedad_relativa': humidity_daily.get(fecha_str, 0.0),
                'riesgo': _riesgo_automatico(temp_min, viento_max, precip),
            }
        return results
