import csv
import io
import json
import urllib.error
import urllib.request

from odoo import fields, models, _
from odoo.exceptions import UserError


class SilicieImportNcWizard(models.TransientModel):
    _name = 'silicie.import.nc.wizard'
    _description = 'Importar códigos NC desde Internet'

    url = fields.Char(
        string='URL del fichero CSV o JSON', required=True,
        help='El fichero debe incluir codigo y descripcion. También puede incluir epigrafe_fiscal.',
    )
    sobrescribir_descripcion = fields.Boolean(
        string='Actualizar descripciones existentes', default=True,
    )
    num_creados = fields.Integer(string='Códigos creados', readonly=True)
    num_actualizados = fields.Integer(string='Códigos actualizados', readonly=True)

    def action_open(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Importar Códigos NC desde Internet'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_importar(self):
        self.ensure_one()
        if not self.url.startswith(('https://', 'http://')):
            raise UserError(_('La URL debe comenzar por http:// o https://.'))

        try:
            request = urllib.request.Request(
                self.url,
                headers={'User-Agent': 'Odoo SILICIE Bodega'},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read(10 * 1024 * 1024 + 1)
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise UserError(_('No se pudo descargar el fichero: %s') % error) from error

        if len(content) > 10 * 1024 * 1024:
            raise UserError(_('El fichero supera el límite de 10 MB.'))
        rows = self._parse_content(content)
        if not rows:
            raise UserError(_('El fichero no contiene códigos NC.'))

        codigo_model = self.env['silicie.codigo.nc']
        created = updated = 0
        for row in rows:
            codigo = str(row.get('codigo') or row.get('codigo_nc') or '').strip()
            descripcion = str(row.get('descripcion') or row.get('description') or '').strip()
            epigrafe = str(row.get('epigrafe_fiscal') or row.get('epigrafe') or '').strip()
            if len(codigo) != 8 or not codigo.isdigit() or not descripcion:
                continue
            record = codigo_model.search([('codigo', '=', codigo)], limit=1)
            values = {'descripcion': descripcion}
            if epigrafe:
                values['epigrafe_fiscal'] = epigrafe
            if record:
                if self.sobrescribir_descripcion or epigrafe:
                    record.write(values)
                    updated += 1
            else:
                if not epigrafe:
                    epigrafe = 'Pendiente de asignar'
                values['codigo'] = codigo
                values['epigrafe_fiscal'] = epigrafe
                codigo_model.create(values)
                created += 1

        if not created and not updated:
            raise UserError(_('No se encontraron filas válidas.'))
        self.write({'num_creados': created, 'num_actualizados': updated})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _parse_content(self, content):
        try:
            text = content.decode('utf-8-sig')
        except UnicodeDecodeError as error:
            raise UserError(_('El fichero debe estar codificado en UTF-8.')) from error

        if self.url.lower().split('?', 1)[0].endswith('.json') or text.lstrip().startswith('['):
            try:
                data = json.loads(text)
            except json.JSONDecodeError as error:
                raise UserError(_('El JSON no es válido: %s') % error) from error
            if isinstance(data, dict):
                data = data.get('items') or data.get('data') or []
            return data if isinstance(data, list) else []

        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
            return list(csv.DictReader(io.StringIO(text), dialect=dialect))
        except csv.Error as error:
            raise UserError(_('El CSV no es válido: %s') % error) from error