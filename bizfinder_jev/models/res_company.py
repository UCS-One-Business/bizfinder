from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Default OFF, and under development (the switch is visible only with
    # ucs_core.development_features): a ride-along on the monitoring feature.
    # Off means the cron and the event form never call Jev; events already
    # triaged keep their labels.
    bizfinder_jev_triage_enabled = fields.Boolean(
        string='AI Event Triage (under development)',
        default=False,
        help='Let TypeSafe Jev sort non-severe Bizfinder events into sales '
             'opportunity, account follow-up or informational, and schedule '
             'an activity for the salesperson on the first two.',
    )
