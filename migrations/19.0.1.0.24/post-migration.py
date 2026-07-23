"""Back-fill Source + the Bizfinder flag onto leads created before 1.0.24.

Leads created by older Bizfinder versions had no Source set and predate the
``is_bizfinder_lead`` flag that drives the new dedicated tab. They are
identifiable by ``company_organisation_number`` (only Bizfinder writes it),
so tag them with the Bizfinder UTM source and light up the flag. We leave the
old leads' notes (``description``) untouched — only new leads route their
imported data into the dedicated ``bizfinder_data`` field/tab.
"""


def migrate(cr, version):
    cr.execute(
        "SELECT res_id FROM ir_model_data "
        "WHERE module = 'bizfinder' AND name = 'utm_source_bizfinder' LIMIT 1"
    )
    row = cr.fetchone()
    if not row:
        return
    source_id = row[0]
    cr.execute(
        """
        UPDATE crm_lead
           SET source_id = %s,
               is_bizfinder_lead = TRUE
         WHERE company_organisation_number IS NOT NULL
           AND source_id IS NULL
        """,
        (source_id,),
    )
