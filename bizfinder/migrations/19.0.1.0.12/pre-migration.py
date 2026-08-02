"""Drop CSV columns replaced by m2m lookups on ``bizfinder.search``.

The wizard moved off free-text comma-joined inputs for buckets, legal
forms, SNI prefixes and municipalities - each became a Many2many to a
proper lookup model. Per AGENTS.md, the corresponding column drops are
explicit DDL here so we don't leave orphaned columns on the transient
table.
"""

_COLUMNS = [
    "employee_buckets",
    "turnover_buckets",
    "legal_forms",
    "sni_prefixes",
    "post_community_names",
    "post_community_codes",
    "registered_community_codes",
    "visiting_community_codes",
]


def migrate(cr, version):
    for col in _COLUMNS:
        cr.execute(f"ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS {col};")
