
import os

from odoo import _, api, fields, models

ENV_BIZFINDER_API_URL = 'BIZFINDER_API_URL'
ENV_BIZFINDER_ACCESS_TOKEN = 'BIZFINDER_ACCESS_TOKEN'  # noqa: S105 - env var name, not a secret

# Production service URL, built in so customer setup is only the access
# token. The only override is the BIZFINDER_API_URL env var (dev/test):
# it is explicit deployment config that cannot silently persist in a
# customer database, unlike the removed per-company URL field, whose
# stale value once sent a bearer token to the wrong host.
DEFAULT_BIZFINDER_API_URL = 'https://bizfinder.se'


def _env_value(name: str) -> str:
    return (os.getenv(name) or '').strip()


class BizfinderSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bizfinder_access_token = fields.Char(
        related='company_id.bizfinder_access_token',
        readonly=False,
    )
    # Feature toggle for the monitoring part. Checking it implies
    # group_bizfinder_monitoring to the salesman group, which reveals the
    # monitoring UI (partner page, events menu, lookup) and arms the daily
    # cron; unchecking hides it all again and the cron no-ops.
    group_bizfinder_monitoring = fields.Boolean(
        string='Company Monitoring',
        implied_group='bizfinder.group_bizfinder_monitoring',
        group='sales_team.group_sale_salesman',
    )

    def action_bizfinder_test_connection(self):
        self.ensure_one()
        self.env['bizfinder.client'].validate()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bizfinder',
                'message': _('Connection to the Bizfinder service succeeded.'),
                'type': 'success',
                'sticky': False,
            },
        }

    @api.model
    def get_bizfinder_credentials(self) -> tuple[str, str]:
        company = self.env.company.sudo()
        return (
            (
                _env_value(ENV_BIZFINDER_API_URL)
                or DEFAULT_BIZFINDER_API_URL
            ).strip(),
            (
                company.bizfinder_access_token
                or _env_value(ENV_BIZFINDER_ACCESS_TOKEN)
            ).strip(),
        )
