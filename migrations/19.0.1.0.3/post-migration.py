# -*- coding: utf-8 -*-
"""Drop the ``take`` column on ``bizfinder.search``.

The result-page size was switched from a configurable wizard field to a
hardcoded constant in :py:meth:`BizfinderSearch.action_search`. Per
AGENTS.md, removing a field requires an explicit DDL drop.
"""


def migrate(cr, version):
    cr.execute("ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS take;")
