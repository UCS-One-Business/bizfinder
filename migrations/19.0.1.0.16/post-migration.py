# -*- coding: utf-8 -*-
"""Re-pull catalogues so industries get populated from the API SNI list."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    # Old curated industries (10 entries) get overwritten by sync;
    # delete them first so users don't see both old and new rows if the
    # API SNI list changed names.
    env.cr.execute("DELETE FROM bizfinder_industry;")
    try:
        env['bizfinder.client'].sync_catalogues()
    except Exception as exc:
        _logger.warning(
            "bizfinder catalogue sync skipped: %s. "
            "Run Settings → Bizfinder → Refresh catalogues once the API is reachable.",
            exc,
        )
