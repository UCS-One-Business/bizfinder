"""Drop the removed suppression-toggle columns.

``exclude_crm_leads`` / ``exclude_partners`` were removed from
``bizfinder.filter.mixin``: suppression of already-known companies is now
always on, with an automatic fallback to result-page deduplication when the
known-company set exceeds the API payload limit. The ORM does not drop the
orphaned columns on upgrade, so do it here.
"""


def migrate(cr, version):
    for table in ('bizfinder_search', 'bizfinder_preset'):
        for col in ('exclude_crm_leads', 'exclude_partners'):
            cr.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS {col}')
