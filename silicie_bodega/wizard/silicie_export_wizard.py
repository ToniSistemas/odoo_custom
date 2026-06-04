import csv
import io
import base64
from datetime import date

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SilicieExportWizard(models.TransientModel):
    _name = 'silicie.export.wizard'
    _description = 'Asistente de exportación SILICIE'

    fecha_desde = fields.Date(
        string='Fecha desde', required=True,
        default=lambda self: date(date.today().year, 1, 1),
    )
    fecha_hasta = fields.Date(
        string='Fecha hasta', required=True,
        default=fields.Date.today,
    )
    solo_confirmados = fields.Boolean(
        string='Solo asientos confirmados',
        default=True,
        help='Si está marcado, solo se exportarán los asientos en estado "Confirmado".',
    )
    marcar_exportado = fields.Boolean(
        string='Marcar como exportados',
        default=True,
        help='Tras exportar, cambia el estado de los asientos a "Exportado".',
    )

    fichero = fields.Binary(string='Fichero SILICIE', readonly=True)
    fichero_nombre = fields.Char(string='Nombre del fichero', readonly=True)
    num_asientos = fields.Integer(string='Asientos exportados', readonly=True)

    def action_exportar(self):
        domain = [
            ('fecha', '>=', self.fecha_desde),
            ('fecha', '<=', self.fecha_hasta),
        ]
        if self.solo_confirmados:
            domain.append(('estado', '=', 'confirmado'))

        asientos = self.env['silicie.asiento'].search(domain, order='fecha asc, name asc')

        if not asientos:
            raise UserError(_('No se encontraron asientos para el período y filtros seleccionados.'))

        output = io.StringIO()
        writer = csv.writer(output, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Cabecera (formato SILICIE 2.0 importación por fichero)
        writer.writerow([
            'NIF_TITULAR',
            'CAE',
            'FECHA_MOVIMIENTO',
            'TIPO_MOVIMIENTO',
            'CODIGO_PRODUCTO',
            'CANTIDAD_LITROS',
            'GRADO_ALCOHOLICO',
            'LITROS_ALCOHOL_PURO',
            'TIPO_JUSTIFICANTE',
            'NUM_JUSTIFICANTE',
            'NIF_ORIGEN_DESTINO',
            'CAE_ORIGEN_DESTINO',
            'NOMBRE_ORIGEN_DESTINO',
            'NUM_ENVASES',
            'CAPACIDAD_ENVASE',
            'OBSERVACIONES',
        ])

        for a in asientos:
            writer.writerow([
                a.nif or '',
                a.cae or '',
                a.fecha.strftime('%d/%m/%Y') if a.fecha else '',
                a.tipo_movimiento or '',
                a.producto_codigo or '',
                '{:.2f}'.format(a.cantidad_litros).replace('.', ','),
                '{:.2f}'.format(a.grado_alcoholico).replace('.', ','),
                '{:.4f}'.format(a.litros_alcohol_puro).replace('.', ','),
                a.justificante_tipo or '',
                a.justificante_numero or '',
                a.origen_destino_nif or '',
                a.origen_destino_cae or '',
                a.origen_destino_nombre or '',
                str(a.num_envases),
                '{:.3f}'.format(a.capacidad_envase).replace('.', ','),
                (a.observaciones or '').replace('\n', ' '),
            ])

        # BOM UTF-8 para compatibilidad con Excel en español
        csv_bytes = '\ufeff'.encode('utf-8') + output.getvalue().encode('utf-8')
        nombre = 'SILICIE_{}_{}_{}.csv'.format(
            a.cae if asientos else 'BODEGA',
            self.fecha_desde.strftime('%Y%m%d'),
            self.fecha_hasta.strftime('%Y%m%d'),
        )

        if self.marcar_exportado:
            asientos.write({'estado': 'exportado'})

        self.write({
            'fichero': base64.b64encode(csv_bytes),
            'fichero_nombre': nombre,
            'num_asientos': len(asientos),
        })

        # Reabrir el wizard para mostrar el enlace de descarga
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'silicie.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
