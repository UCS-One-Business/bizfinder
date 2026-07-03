# -*- coding: utf-8 -*-

import os

from odoo import _, api, fields, models


ENV_BIZFINDER_API_URL = 'BIZFINDER_API_URL'
ENV_BIZFINDER_ACCESS_TOKEN = 'BIZFINDER_ACCESS_TOKEN'

# Production service URL, built in so customer setup is only the access
# token. Dev/test overrides stay possible via the (UI-hidden) per-company
# field or the BIZFINDER_API_URL env var — see get_bizfinder_credentials.
DEFAULT_BIZFINDER_API_URL = 'https://bizfinder.se'


def _env_value(name: str) -> str:
    return (os.getenv(name) or '').strip()


class BizfinderSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bizfinder_api_url = fields.Char(
        related='company_id.bizfinder_api_url',
        readonly=False,
    )
    bizfinder_access_token = fields.Char(
        related='company_id.bizfinder_access_token',
        readonly=False,
    )

    def action_bizfinder_sync_catalogues(self):
        """Pull kommun / SNI / bucket / legal-form catalogues from the
        API. Exposed as a settings button so admins can recover if the
        post-migration seed call failed (e.g. API unreachable at install)."""
        self.ensure_one()
        self.env['bizfinder.client'].sync_catalogues()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bizfinder',
                'message': _('Catalogues refreshed from the API.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_bizfinder_test_connection(self):
        self.ensure_one()
        self.env['bizfinder.client'].validate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bizfinder',
                'message': _('Connection to the Bizfinder service succeeded.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def get_bizfinder_credentials(self) -> tuple[str, str]:
        company = self.env.company.sudo()
        return (
            (
                company.bizfinder_api_url
                or _env_value(ENV_BIZFINDER_API_URL)
                or DEFAULT_BIZFINDER_API_URL
            ).strip(),
            (
                company.bizfinder_access_token
                or _env_value(ENV_BIZFINDER_ACCESS_TOKEN)
            ).strip(),
        )
