"""Drop the per-company Bizfinder API URL override.

The service URL is built into the module (DEFAULT_BIZFINDER_API_URL); a
stale per-company value once redirected requests — bearer token included —
to the wrong host. The ORM does not drop columns for removed fields, so do
it here on both the company table and the transient settings table.
"""


def migrate(cr, version):
    cr.execute("ALTER TABLE res_company DROP COLUMN IF EXISTS bizfinder_api_url")
    cr.execute(
        "ALTER TABLE res_config_settings DROP COLUMN IF EXISTS bizfinder_api_url"
    )
