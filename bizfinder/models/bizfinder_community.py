
from odoo import api, fields, models


class BizfinderCommunity(models.Model):
    """Swedish kommun.

    The ``community_code`` value Creditsafe ships is only the
    kommun-within-län part of the SCB kommunkod, so it repeats across
    län. The unique natural key is therefore the composite
    ``kommunkod = region_code * 100 + community_code`` - which is the
    full SCB code most lookup tables already use.
    """
    _name = 'bizfinder.community'
    _description = 'Swedish kommun'
    _order = 'name, region_id'
    _rec_name = 'display_name'

    kommunkod = fields.Integer(string='SCB kommunkod', required=True, index=True)
    community_code = fields.Integer(string='Community code', required=True)
    name = fields.Char(required=True, translate=False)
    region_id = fields.Many2one('bizfinder.region', ondelete='set null')
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _kommunkod_uniq = models.Constraint(
        'unique(kommunkod)',
        'SCB kommunkod must be unique.',
    )

    @api.depends('name', 'region_id', 'kommunkod')
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.region_id:
                rec.display_name = f"{rec.name} ({rec.region_id.name})"
            elif rec.name:
                rec.display_name = rec.name
            else:
                rec.display_name = str(rec.kommunkod or '')
