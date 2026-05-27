# -*- coding: utf-8 -*-
"""Re-pull the kommun catalogue under the new (region, code) schema."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env['bizfinder.client'].sync_catalogues()
    except Exception as exc:
        _logger.warning(
            "bizfinder catalogue sync skipped: %s. "
            "Run Settings → Bizfinder → Refresh catalogues once the API is reachable.",
            exc,
        )
