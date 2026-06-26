# -*- coding: utf-8 -*-

from odoo import fields, models


class BizfinderPreset(models.Model):
    """A user-saved filter preset for the Bizfinder search wizard.

    Unlike the API-provided segments (which are read-only and sourced from
    ``/api/insight/segments``), these presets are owned and managed inside
    Odoo: a salesperson saves the current wizard filters as a named preset
    and can later re-apply, rename, re-save or delete it. The filter payload
    is stored verbatim in the same JSON shape ``bizfinder.search._build_values``
    produces, so applying a preset reuses the exact same resolution path the
    API segments use.
    """
    _name = 'bizfinder.preset'
    _description = 'Bizfinder Saved Preset'
    _order = 'name'

    name = fields.Char(required=True)
    description = fields.Text(
        help="Optional note shown when this preset is selected.",
    )
    # JSON list of {filterCategory, SelectOption|SelectRange} dicts — the
    # output of bizfinder.search._build_values(). Stored opaque; the wizard
    # decodes it back into form fields via _filters_to_vals().
    filters_json = fields.Text(required=True, default='[]')
    user_id = fields.Many2one(
        'res.users',
        string='Owner',
        default=lambda self: self.env.user,
        ondelete='set null',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        ondelete='cascade',
    )

    _name_uniq = models.Constraint(
        'unique(name, company_id)',
        'A preset with this name already exists for this company.',
    )
