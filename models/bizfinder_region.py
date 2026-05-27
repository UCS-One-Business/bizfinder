# -*- coding: utf-8 -*-

from odoo import fields, models


class BizfinderRegion(models.Model):
    """Swedish counties (län), keyed by SCB region code.

    Used as the multi-select source on the prospect search wizard so reps
    pick regions by name rather than typing numeric codes.
    """
    _name = 'bizfinder.region'
    _description = 'Swedish region (län)'
    _order = 'name'
    _rec_name = 'name'

    code = fields.Integer(string='Region code', required=True, index=True)
    name = fields.Char(string='Name', required=True, translate=False)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Region code must be unique.',
    )
