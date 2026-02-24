Nota Albarán Entrega - Addon para Odoo 17 CE

Estructura creada:
- models/nota_albaran.py
- views/nota_albaran_views.xml
- security/ir.model.access.csv
- views/stock_picking_views.xml
- views/report_picking_templates.xml

Instalación:
1. Copiar la carpeta `nota_albaran_entrega` al directorio de addons de Odoo o usar la carpeta `odoo_custom/nota_albaran_entrega`.
2. Reiniciar el servidor Odoo y actualizar la lista de módulos.
3. Buscar "Nota Albarán Entrega" e instalar.

Nota: Este módulo añade el campo `sale_note` heredado de `sale.order` en `stock.picking` y lo muestra en el informe PDF del albarán.
