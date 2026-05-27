# -*- coding: utf-8 -*-
"""Drop the redundant ``bizfinder.sni`` model and its m2m relation.

The Industries picker (``bizfinder.industry``) is now the single
SNI-backed lookup, populated from the same API endpoint that used to
back ``bizfinder.sni``. Removing the model + relation table here keeps
the schema clean and prevents Odoo from preserving the orphan tables.
"""


def migrate(cr, version):
    cr.execute("DROP TABLE IF EXISTS bizfinder_search_sni_rel CASCADE;")
    cr.execute("DROP TABLE IF EXISTS bizfinder_sni CASCADE;")
    cr.execute("DELETE FROM ir_model WHERE model = 'bizfinder.sni';")
    cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.model' "
        "AND name = 'model_bizfinder_sni';"
    )
