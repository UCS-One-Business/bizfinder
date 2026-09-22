from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bizfinder_jev_triage_enabled = fields.Boolean(
        related='company_id.bizfinder_jev_triage_enabled',
        readonly=False,
    )
