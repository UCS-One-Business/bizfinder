"""Backfill Swedish translations on the built-in segment presets.

From 1.0.34 ``bizfinder.preset`` name/description are translatable and the
Swedish texts for the 15 API segments ship in ``BUILTIN_SEGMENT_SV``. New
seedings get them automatically; this writes them onto presets seeded by
earlier versions. Presets renamed by a user are left alone, and the step is
a no-op when sv_SE is not an active language.
"""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    updated = env['bizfinder.preset']._write_builtin_sv()
    if updated:
        _logger.info(
            "bizfinder: wrote Swedish translations on %s built-in preset(s)",
            updated,
        )
