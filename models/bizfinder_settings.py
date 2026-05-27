# -*- coding: utf-8 -*-

import os

from odoo import api, fields, models


DEFAULT_BIZFINDER_API_URL = 'http://host.docker.internal:8001'
ENV_BIZFINDER_API_URL = 'BIZFINDER_API_URL'
ENV_BIZFINDER_API_KEY = 'BIZFINDER_API_KEY'


def _env_default(name: str, fallback: str = '') -> str:
    return os.getenv(name) or fallback


class BizfinderSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bizfinder_api_url = fields.Char(
        string='Bizfinder API URL',
        config_parameter='bizfinder.api_url',
        default=lambda self: _env_default(ENV_BIZFINDER_API_URL, DEFAULT_BIZFINDER_API_URL),
    )
    bizfinder_api_key = fields.Char(
        string='Bizfinder API Key',
        config_parameter='bizfinder.api_key',
        default=lambda self: _env_default(ENV_BIZFINDER_API_KEY),
    )

    @api.model
    def get_bizfinder_credentials(self) -> tuple[str, str]:
        ICP = self.env['ir.config_parameter'].sudo()
        return (
            ICP.get_param('bizfinder.api_url')
            or _env_default(ENV_BIZFINDER_API_URL, DEFAULT_BIZFINDER_API_URL),
            ICP.get_param('bizfinder.api_key')
            or _env_default(ENV_BIZFINDER_API_KEY),
        )
