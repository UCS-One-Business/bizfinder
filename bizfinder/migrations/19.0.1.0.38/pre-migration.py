"""Adopt API-synced catalogue rows into the new seeded XML IDs.

19.0.1.0.38 ships the kommun / SNI / legal-form catalogues as noupdate
module data (data/bizfinder_*_data.xml) instead of requiring an API
sync at install. Databases upgraded from earlier versions already hold
those rows - created by sync_catalogues() and therefore WITHOUT XML
IDs. Loading the data files against them would try to create duplicates
and crash on the unique constraints (kommunkod / legal-form code).

So, before the data files load, bind every existing row to the XML ID
the seed will use, keyed on the same natural keys sync_catalogues()
upserts by. Rows that already have an XML ID (or databases where the
seeds already loaded) are skipped, so the migration is idempotent.
"""


def _bind(cr, model, table, name_sql, where_sql="TRUE"):
    cr.execute(
        f"""
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        SELECT 'bizfinder', {name_sql}, %s, t.id, TRUE
        FROM {table} t
        WHERE {where_sql}
        AND NOT EXISTS (
            SELECT 1 FROM ir_model_data d
            WHERE d.module = 'bizfinder' AND d.name = {name_sql}
        )
        AND NOT EXISTS (
            SELECT 1 FROM ir_model_data d
            WHERE d.model = %s AND d.res_id = t.id
        )
        """,
        (model, model),
    )


def migrate(cr, version):
    # Communities: community_se_<4-digit SCB kommunkod>.
    _bind(
        cr,
        "bizfinder.community",
        "bizfinder_community",
        "'community_se_' || lpad(t.kommunkod::text, 4, '0')",
    )
    # Industries: only the 1:1 SNI-division rows sync created (a bare
    # 2-digit code in sni_prefixes). Hand-curated multi-prefix shortcuts
    # keep living without XML IDs, untouched by the seeds.
    _bind(
        cr,
        "bizfinder.industry",
        "bizfinder_industry",
        "'industry_sni_' || t.sni_prefixes",
        where_sql=r"t.sni_prefixes ~ '^\d{2}$'",
    )
    # Legal forms: slugged code (AB -> ab, HB/KB -> hb_kb, OVR -> ovr).
    _bind(
        cr,
        "bizfinder.legal.form",
        "bizfinder_legal_form",
        "'legal_form_' || replace(lower(t.code), '/', '_')",
    )
