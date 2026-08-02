"""Drop the old hand-curated industries (10 entries).

They used multi-prefix sni_prefixes values that clash with the 1:1
SNI-division catalogue. The rows are repopulated by the seed data files
(data/bizfinder_industry_data.xml, shipped since 19.0.1.0.38) when the
upgrade loads module data.
"""

from odoo.tools.sql import table_exists


def migrate(cr, version):
    if table_exists(cr, "bizfinder_industry"):
        cr.execute("DELETE FROM bizfinder_industry;")
