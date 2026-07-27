"""Collapse buckets + zip fields on ``bizfinder.search``.

The fine-grained ``employee_bucket_ids`` / ``turnover_bucket_ids``
pickers were redundant with the magnitude pickers at the top of the
form, so they're removed along with the ``bizfinder.bucket`` model
that backed them.

The three per-address ZIP-prefix Char columns are replaced by a single
``zip_prefixes`` Char that the wizard now sends as a new ``ZIP_ANY``
filter (OR'd across all three zipcode columns on the API side).
"""

_COLUMNS = [
    "post_zip_prefixes",
    "registered_zip_prefixes",
    "visiting_zip_prefixes",
]

_REL_TABLES = [
    "bizfinder_search_employee_bucket_rel",
    "bizfinder_search_turnover_bucket_rel",
]


def migrate(cr, version):
    for col in _COLUMNS:
        cr.execute(f"ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS {col};")
    for tbl in _REL_TABLES:
        cr.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE;")
    cr.execute("DROP TABLE IF EXISTS bizfinder_bucket CASCADE;")
    cr.execute("DELETE FROM ir_model WHERE model = 'bizfinder.bucket';")
    cr.execute(
        "DELETE FROM ir_model_data WHERE model = 'ir.model' "
        "AND name = 'model_bizfinder_bucket';"
    )
