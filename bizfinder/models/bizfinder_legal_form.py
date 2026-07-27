
from odoo import fields, models


class BizfinderLegalForm(models.Model):
    """Swedish legal-form group (bolagsform). Small enumeration mirroring
    the API ``LEGALGROUP_CODE`` values."""
    _name = 'bizfinder.legal.form'
    _description = 'Swedish legal form'
    _order = 'sequence, code'
    _rec_name = 'name'

    code = fields.Char(required=True, index=True)
    name = fields.Char(required=True, translate=False)
    sequence = fields.Integer(default=10)

    _code_uniq = models.Constraint(
        'unique(code)',
        'Legal form code must be unique.',
    )
