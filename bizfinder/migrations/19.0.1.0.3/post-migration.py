"""Drop the ``take`` column on ``bizfinder.search``.

The result-page size was switched from a configurable wizard field to a
hardcoded constant in :py:meth:`BizfinderSearch.action_search`. Per
AGENTS.md, removing a field requires an explicit DDL drop.
"""

from odoo.tools.sql import column_exists


def migrate(cr, version):
    if column_exists(cr, "bizfinder_search", "take"):
        cr.execute("ALTER TABLE bizfinder_search DROP COLUMN take;")
