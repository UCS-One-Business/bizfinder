
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Swedish texts for the built-in API segments, keyed by segment key. The API
# serves segment name/description in English only, so the Swedish side is
# maintained here and written as sv_SE field translations when the built-ins
# are seeded (and backfilled by the 19.0.1.0.34 migration). ``en`` is the
# canonical English segment name at authoring time: it guards the write so a
# preset the user has renamed is left alone.
BUILTIN_SEGMENT_SV = {
    'hot_growth': {
        'en': 'Up-and-coming SMEs',
        'name': 'SMB på uppgång',
        'description': "Aktiebolag med omsättningstillväxt ≥ 15 % och rörelsemarginal ≥ 5 %, "
                       "soliditet ≥ 25 %, 5–49 anställda, registrerade för F-skatt. Den heta "
                       "SMB-listan säljarna faktiskt vill ringa.",
    },
    'newborns': {
        'en': 'Newly formed AB',
        'name': 'Nybildade AB',
        'description': "Aktiebolag bildade under de senaste 6 månaderna, med F-skatt. Alla "
                       "redovisningsbyråer, banker och B2B SaaS-leverantörer vill åt dessa.",
    },
    'stable_profitable': {
        'en': 'Stable & profitable',
        'name': 'Stabila & lönsamma',
        'description': "Aktiebolag med vinstmarginal ≥ 10 %, soliditet ≥ 40 %, helårsbokslut "
                       "(≥ 12 månader) och F-skatt. Mogna verksamheter; passar tjänster med "
                       "högt kontraktsvärde.",
    },
    'cash_rich_smb': {
        'en': 'Cash-rich SMEs',
        'name': 'Kassastarka SMB',
        'description': "Aktiebolag med kassa och bank ≥ 1 Mkr, kassalikviditet ≥ 100 %, "
                       "5–49 anställda. Likviditet för nya leverantörsåtaganden.",
    },
    'mid_market_ab': {
        'en': 'Mid-market AB',
        'name': 'Mellanstora AB',
        'description': "Aktiebolag med 50–199 anställda, F-skatt och reviderade bokslut. Det "
                       "mest attraktiva affärsstorlekssegmentet för B2B SaaS och tjänster.",
    },
    'past_first_year': {
        'en': 'Past first year',
        'name': 'Klarat första året',
        'description': "Aktiebolag bildade för 12–24 månader sedan, med F-skatt. Förbi "
                       "startup-smekmånaden — köper riktiga verktyg nu.",
    },
    'distressed_operating': {
        'en': 'Distressed but operating',
        'name': 'Pressade men aktiva',
        'description': "Aktiva aktiebolag med revisorsanmärkning under de senaste 24 månaderna. "
                       "Omvänd spelbok: factoring, rekonstruktion, turnaround-rådgivning, "
                       "juridiska tjänster.",
    },
    'recovery_candidates': {
        'en': 'Recovery candidates',
        'name': 'Återhämtningskandidater',
        'description': "Aktiebolag med omsättningstillväxt mellan -25 % och -5 %, soliditet "
                       "≥ 20 %, fortfarande positivt eget kapital. Negativ tillväxt men "
                       "solventa — turnaround-rådgivning och kostnadsbesparande verktyg.",
    },
    'it_growers': {
        'en': 'IT consulting growers',
        'name': 'Växande IT-konsulter',
        'description': "Aktiebolag inom SNI 62 (programmering/IT-konsult), omsättningstillväxt "
                       "≥ 15 %, personaltillväxt ≥ 10 %, 5–199 anställda. Branschpreset — "
                       "klona för andra branscher.",
    },
    'construction_sme': {
        'en': 'Construction SMEs',
        'name': 'Bygg-SMB',
        'description': "Aktiebolag inom SNI 41 (byggande av hus) eller 43 (specialiserad "
                       "bygg- och anläggningsverksamhet), 5–49 anställda, med F-skatt. "
                       "Fastigheter, materiel och programvara för byggbranschen.",
    },
    'scaleups': {
        'en': 'Scaleups',
        'name': 'Scaleups',
        'description': "Aktiebolag med omsättningstillväxt ≥ 25 %, personaltillväxt ≥ 10 %, "
                       "5–49 anställda, med F-skatt. Bolag som faktiskt skalar — kombinera "
                       "med länsfältet för territoriebearbetning.",
    },
    'high_dividend': {
        'en': 'Dividend payers',
        'name': 'Utdelningsbolag',
        'description': "Aktiebolag med utdelning ≥ 500 tkr senaste året, soliditet ≥ 30 %. "
                       "Ägaruttagna vinster — förmögenhetsförvaltning, skatterådgivning, "
                       "generationsskifte.",
    },
    'multi_unit_ops': {
        'en': 'Multi-location operations',
        'name': 'Verksamhet på flera orter',
        'description': "Aktiebolag med 3+ arbetsställen. Franchise, butikskedjor, "
                       "servicenätverk — kassasystem, logistik, multi-site-hantering.",
    },
    'enterprise_candidates': {
        'en': 'Enterprise candidates',
        'name': 'Enterprise-kandidater',
        'description': "Aktiebolag med nettoomsättning ≥ 50 Mkr, 100+ anställda, med F-skatt. "
                       "Storaffärssegmentet — långa säljcykler, höga kontraktsvärden.",
    },
    'equity_rich': {
        'en': 'Equity-rich AB',
        'name': 'Kapitalstarka AB',
        'description': "Aktiebolag med eget kapital ≥ 5 Mkr och soliditet ≥ 50 %. Kapital "
                       "redo för investeringar — capex, M&A-rådgivning, kapitalförvaltning.",
    },
}


class BizfinderPreset(models.Model):
    """A managed, fully-editable search preset.

    Holds the same filter fields as the search wizard (via the shared
    bizfinder.filter.mixin), so a preset can be configured on a form that
    mirrors the prospect search form. The 15 built-in segments shipped by the
    API are seeded into these records (``key`` set) and from then on are
    managed like any other preset.
    """
    _name = 'bizfinder.preset'
    _inherit = 'bizfinder.filter.mixin'
    _description = 'Bizfinder Preset'
    _order = 'name'

    name = fields.Char(required=True, translate=True)
    description = fields.Text(
        translate=True,
        help="Shown when this preset is selected on the prospect search.",
    )
    # Set for presets seeded from an API segment; blank for user-created ones.
    # Used as the idempotency key when (re)seeding the built-ins.
    key = fields.Char(string='Built-in key', readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        ondelete='cascade',
    )

    # Own relation tables (distinct from bizfinder.search's) — see the mixin
    # docstring for why these aren't declared on the abstract model.
    region_ids = fields.Many2many(
        'bizfinder.region',
        'bizfinder_preset_region_rel', 'preset_id', 'region_id',
        string='Regions',
        help="Pick one or more Swedish counties (län) to limit the search.",
    )
    industry_ids = fields.Many2many(
        'bizfinder.industry',
        'bizfinder_preset_industry_rel', 'preset_id', 'industry_id',
        string='Industries',
        help="Curated industry shortcuts. Each expands to its SNI prefixes.",
    )
    employee_magnitude_ids = fields.Many2many(
        'bizfinder.magnitude',
        'bizfinder_preset_employee_magnitude_rel', 'preset_id', 'magnitude_id',
        string='Employees',
        domain="[('kind', '=', 'employees')]",
        help="Find companies by how many people they employ. Pick one or "
             "more size bands. Leave empty to include every size.",
    )
    net_sales_magnitude_ids = fields.Many2many(
        'bizfinder.magnitude',
        'bizfinder_preset_net_sales_magnitude_rel', 'preset_id', 'magnitude_id',
        string='Turnover',
        domain="[('kind', '=', 'net_sales')]",
        help="Find companies by their yearly revenue. Pick one or more "
             "ranges. Leave empty to include every size.",
    )
    post_community_ids = fields.Many2many(
        'bizfinder.community',
        'bizfinder_preset_post_community_rel', 'preset_id', 'community_id',
        string='Municipalities (postal)',
        help="Postal-address kommun. Start typing to filter.",
    )
    alt_community_ids = fields.Many2many(
        'bizfinder.community',
        'bizfinder_preset_alt_community_rel', 'preset_id', 'community_id',
        string='Kommun',
        help="Matches registered OR visiting address kommun.",
    )
    legal_form_ids = fields.Many2many(
        'bizfinder.legal.form',
        'bizfinder_preset_legal_form_rel', 'preset_id', 'legal_form_id',
        string='Legal forms',
    )

    _name_company_uniq = models.Constraint(
        'unique(name, company_id)',
        'A preset with this name already exists for this company.',
    )

    @api.model
    def _seed_builtin_presets(self) -> int:
        """Create a managed preset for each API segment that isn't seeded yet.

        Idempotent and non-destructive: matches on ``key`` and only creates
        missing ones, so edits to already-seeded presets survive re-seeding.
        Returns the number of presets created.
        """
        segments = self.env['bizfinder.client'].get_segments()
        existing_keys = set(
            self.sudo().with_context(active_test=False)
            .search([('key', '!=', False)]).mapped('key')
        )
        created = 0
        for seg in segments:
            key = seg.get('key')
            if not key or key in existing_keys:
                continue
            preset = self.create({
                'name': seg.get('name') or key,
                'description': seg.get('description') or '',
                'key': key,
            })
            preset.write(preset._resolve_filters_to_vals(seg.get('filters') or []))
            # Prefer the translations served with the segment; fall back to
            # the local table for API versions that don't ship i18n yet.
            if not self._write_builtin_i18n(preset, seg.get('i18n')):
                self._write_builtin_sv(preset)
            created += 1
        if created:
            _logger.info("bizfinder: seeded %s built-in preset(s)", created)
        return created

    @api.model
    def _write_builtin_i18n(self, preset, i18n) -> int:
        """Write the per-language name/description translations served in a
        segment payload (``{lang_code: {'name': .., 'description': ..}}``)
        onto a freshly seeded preset. Languages not active in this database
        are skipped. Returns the number of languages written."""
        # Active languages only — a handful of records at most.
        active = set(self.env['res.lang'].search([]).mapped('code'))  # pylint: disable=no-search-all
        written = 0
        for lang, texts in (i18n or {}).items():
            if lang not in active or not isinstance(texts, dict):
                continue
            vals = {
                field: texts[field]
                for field in ('name', 'description') if texts.get(field)
            }
            if vals:
                preset.with_context(lang=lang).write(vals)
                written += 1
        return written

    @api.model
    def _write_builtin_sv(self, presets=None) -> int:
        """Write the Swedish (sv_SE) name/description translations onto
        built-in presets. The API only serves the English texts, so the
        Swedish side lives in ``BUILTIN_SEGMENT_SV``.

        Idempotent; skips presets whose English name no longer matches the
        canonical segment name (i.e. renamed by a user). No-op when sv_SE is
        not an active language. Returns the number of presets updated."""
        if not self.env['res.lang'].search_count(
            [('code', '=', 'sv_SE'), ('active', '=', True)], limit=1
        ):
            return 0
        if presets is None:
            presets = self.sudo().with_context(active_test=False).search(
                [('key', 'in', list(BUILTIN_SEGMENT_SV))]
            )
        updated = 0
        for preset in presets:
            texts = BUILTIN_SEGMENT_SV.get(preset.key)
            if not texts:
                continue
            if preset.with_context(lang='en_US').name != texts['en']:
                continue
            preset.with_context(lang='sv_SE').write({
                'name': texts['name'],
                'description': texts['description'],
            })
            updated += 1
        return updated
