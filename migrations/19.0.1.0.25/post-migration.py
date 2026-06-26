# -*- coding: utf-8 -*-
"""Move presets onto real filter fields and seed the built-in segments.

1.0.24 stored a preset's filters as a ``filters_json`` blob. From 1.0.25 a
preset carries the same filter fields as the search wizard, so decode any
existing blob into those fields. Then seed the 15 API segments as managed
presets (idempotent). Both steps are best-effort — the API may be unreachable
at upgrade time, in which case the built-ins can be seeded later from
Settings -> Refresh catalogues.
"""

import json
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Preset = env['bizfinder.preset']

    # Decode legacy filters_json (column left behind by Odoo) into fields.
    try:
        cr.execute("""
            SELECT id, filters_json FROM bizfinder_preset
             WHERE filters_json IS NOT NULL AND filters_json NOT IN ('', '[]')
        """)
        rows = cr.fetchall()
    except Exception:  # column absent (fresh table) — nothing to convert
        rows = []
    for pid, blob in rows:
        try:
            filters = json.loads(blob)
            preset = Preset.browse(pid)
            preset.write(preset._resolve_filters_to_vals(filters))
        except Exception as exc:
            _logger.warning("bizfinder: could not convert preset %s: %s", pid, exc)

    # Seed the built-in segments as managed presets.
    try:
        Preset._seed_builtin_presets()
    except Exception as exc:
        _logger.warning(
            "bizfinder: built-in presets not seeded (API unreachable?): %s. "
            "Run Settings -> Refresh catalogues to seed them.", exc)
