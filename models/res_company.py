# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bizfinder_access_token = fields.Char(
        string='Bizfinder Access Token',
        help='Customer tenant token issued by the Bizfinder service.',
    )
