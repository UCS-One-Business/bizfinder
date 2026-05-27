# -*- coding: utf-8 -*-
"""Move legacy global Bizfinder credentials onto companies."""


def migrate(cr, version):
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    ICP = env['ir.config_parameter'].sudo()
    api_url = (ICP.get_param('bizfinder.api_url') or '').strip()
    access_token = (ICP.get_param('bizfinder.api_key') or '').strip()
    if not api_url and not access_token:
        return

    for company in env['res.company'].sudo().search([]):
        vals = {}
        if api_url and not company.bizfinder_api_url:
            vals['bizfinder_api_url'] = api_url
        if access_token and not company.bizfinder_access_token:
            vals['bizfinder_access_token'] = access_token
        if vals:
            company.write(vals)
