"""Drop the obsolete ``show_advanced`` column on ``bizfinder.search``.

The advanced-filters toggle is now pure client-side ``<details>``/``<summary>``
so the boolean field that backed the server-driven toggle is no longer
needed. Per AGENTS.md, removing a field requires an explicit DDL drop;
the ORM does not clean up unused columns on upgrade.
"""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS show_advanced;"
    )
