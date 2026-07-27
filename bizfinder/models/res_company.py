
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bizfinder_access_token = fields.Char(
        help='Customer tenant token issued by the Bizfinder service.',
    )
