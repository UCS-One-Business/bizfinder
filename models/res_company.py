# -*- coding: utf-8 -*-

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    bizfinder_api_url = fields.Char(
        string='Bizfinder API URL',
        help='Dev/test override of the built-in Bizfinder service URL. '
             'Leave empty in production: the module targets the official '
             'service by default and customers only configure their token.',
    )
    bizfinder_access_token = fields.Char(
        string='Bizfinder Access Token',
        help='Customer tenant token issued by the Bizfinder service.',
    )
