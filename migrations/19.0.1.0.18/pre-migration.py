"""Drop old month-based date columns + the separate alt-address pickers.

The wizard now exposes real Date pickers (registration_date_from/to,
formed_date_from/to, etc.) instead of Char "months ago" inputs, and a
single ``alt_community_ids`` m2m that replaces the separate registered
/ visiting community + visiting region pickers.
"""

_COLUMNS = [
    "registered_min_months",
    "registered_max_months",
    "formed_min_months",
    "formed_max_months",
    "status_changed_min_months",
    "status_changed_max_months",
    "reservation_min_months",
    "reservation_max_months",
]

_REL_TABLES = [
    "bizfinder_search_registered_community_rel",
    "bizfinder_search_visiting_community_rel",
    "bizfinder_search_visiting_region_rel",
]


def migrate(cr, version):
    for col in _COLUMNS:
        cr.execute(f"ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS {col};")
    for tbl in _REL_TABLES:
        cr.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
