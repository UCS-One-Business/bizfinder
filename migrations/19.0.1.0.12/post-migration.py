# -*- coding: utf-8 -*-
"""Seed the kommun / SNI / bucket / legal-form lookup tables.

Best-effort: if the API is unreachable at upgrade time the catalogues
stay empty and the admin can refresh them later from the Bizfinder
settings page. We don't raise — that would block the upgrade.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        env['bizfinder.client'].sync_catalogues()
    except Exception as exc:
        _logger.warning(
            "bizfinder catalogue sync skipped during upgrade: %s. "
            "Run Settings → Bizfinder → Refresh catalogues once the API is reachable.",
            exc,
        )
