"""Drop the Formed date filter — it was redundant with Registered
for the use cases users actually run."""


def migrate(cr, version):
    for col in ("formed_date_from", "formed_date_to"):
        cr.execute(f"ALTER TABLE bizfinder_search DROP COLUMN IF EXISTS {col};")
