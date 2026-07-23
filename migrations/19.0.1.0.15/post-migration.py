"""Move legacy global Bizfinder credentials onto companies."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()
    # The legacy bizfinder.api_url parameter is intentionally NOT migrated:
    # the per-company URL override was removed in 19.0.1.0.39 (the service
    # URL is built in), and this migration may run with that newer code.
    access_token = (ICP.get_param('bizfinder.api_key') or '').strip()
    if not access_token:
        return

    for company in env['res.company'].sudo().search([]):
        if not company.bizfinder_access_token:
            company.bizfinder_access_token = access_token
