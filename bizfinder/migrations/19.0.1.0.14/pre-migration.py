"""Reshape ``bizfinder.community`` to key on the composite SCB kommunkod.

The previous unique-on-``code`` schema treated Creditsafe's
community_code as authoritative, but that value repeats across län
(it's only the kommun-within-län part of the SCB kommunkod). We now
key on the 4-digit composite ``kommunkod = region*100 + community``
instead.

The table starts empty (the catalogue is API-fetched), so we just drop
the old column + constraint and let the ORM (re)create the new shape.
The post-update sync_catalogues() call then repopulates it.
"""


def migrate(cr, version):
    cr.execute(
        "ALTER TABLE bizfinder_community "
        "DROP CONSTRAINT IF EXISTS bizfinder_community_code_uniq;"
    )
    cr.execute("ALTER TABLE bizfinder_community DROP COLUMN IF EXISTS code;")
    # Clear stale rows from the prior schema - kommunkod cannot be
    # backfilled without region info, and the API call in the
    # post-migration will repopulate cleanly.
    cr.execute("DELETE FROM bizfinder_community;")
