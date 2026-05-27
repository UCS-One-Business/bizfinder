# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bizfinder_api_url = fields.Char(
        string='Bizfinder API URL',
        help='Base URL for the Bizfinder service used by this company.',
    )
    bizfinder_access_token = fields.Char(
        string='Bizfinder Access Token',
        help='Customer tenant token issued by the Bizfinder service.',
    )
