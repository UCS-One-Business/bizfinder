# -*- coding: utf-8 -*-

import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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

    name = fields.Char(required=True)
    description = fields.Text(
        help="Shown when this preset is selected on the prospect search.",
    )
    # Set for presets seeded from an API segment; blank for user-created ones.
    # Used as the idempotency key when (re)seeding the built-ins.
    key = fields.Char(string='Built-in key', readonly=True, copy=False)
    company_id = fields.Many2one(
        'res.company',
        string='Company',
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
            created += 1
        if created:
            _logger.info("bizfinder: seeded %s built-in preset(s)", created)
        return created
