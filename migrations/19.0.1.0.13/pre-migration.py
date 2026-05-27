# -*- coding: utf-8 -*-
"""Drop ``units_min`` / ``units_max`` and the now-removed
``industry_preset`` selection column on ``bizfinder.search``.

The "number of units" range filter was dropped from the UI — it never
mapped to anything users actually wanted to slice on. ``industry_preset``
was replaced by the new ``industry_ids`` Many2many.
"""

_COLUMNS = [
    "units_min",
    "units_max",
    "industry_preset",
]


def migrate(cr, version):
    for col in _COLUMNS:
        cr.execute(f"ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS {col};")
