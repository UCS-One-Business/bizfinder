"""Drop the per-company Bizfinder API URL override.

The service URL is built into the module (DEFAULT_BIZFINDER_API_URL); a
stale per-company value once redirected requests - bearer token included -
to the wrong host. The ORM does not drop columns for removed fields, so do
it here on both the company table and the transient settings table.
"""

from odoo.tools.sql import column_exists


def migrate(cr, version):
    for table in ("res_company", "res_config_settings"):
        if column_exists(cr, table, "bizfinder_api_url"):
            cr.execute(f"ALTER TABLE {table} DROP COLUMN bizfinder_api_url")
