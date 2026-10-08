def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    templates = env['product.template'].with_context(active_test=False).search([])
    env.add_to_compute(templates._fields['manufacturer_reference'], templates)
    templates.flush_recordset(['manufacturer_reference'])
