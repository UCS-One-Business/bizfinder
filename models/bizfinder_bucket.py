# -*- coding: utf-8 -*-

from odoo import fields, models


class BizfinderBucket(models.Model):
    """Turnover / employee bucket. The ``key`` is the literal Swedish
    enum string the API expects (e.g. ``5-9 anställda``) and must be
    round-tripped unchanged into the filter payload."""
    _name = 'bizfinder.bucket'
    _description = 'Bizfinder bucket'
    _order = 'kind, sequence, key'
    _rec_name = 'key'

    kind = fields.Selection(
        [('employees', 'Employees'), ('turnover', 'Turnover')],
        required=True, index=True,
    )
    key = fields.Char(string='API key', required=True, index=True)
    sequence = fields.Integer(default=10)

    _key_uniq = models.Constraint(
        'unique(kind, key)',
        'Bucket key must be unique per kind.',
    )
