
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Max orgNumbers per company-status / events API call (contract limit is 5000;
# stay well under it so a single batch stays fast and failures stay small).
BATCH_SIZE = 1000

# Health thresholds (percent). Kept as module constants next to
# _bizfinder_classify_health so tuning the rule is a one-place edit.
SOLIDITY_CRITICAL_BELOW = 10.0
SOLIDITY_WARNING_BELOW = 20.0
GROWTH_WARNING_BELOW = -10.0
QUICK_RATIO_WARNING_BELOW = 75.0

STATUS_CODE_ACTIVE = 100


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # --- registry status, written by the sync (readonly in the UI) ---------
    bizfinder_status_code = fields.Integer(string='Registry status code', readonly=True)
    bizfinder_status_text = fields.Char(string='Registry status', readonly=True)
    bizfinder_active = fields.Boolean(string='Active in registry', readonly=True)
    bizfinder_f_tax = fields.Selection(
        [('yes', 'Yes'), ('no', 'No'), ('unknown', 'Unknown')],
        string='F-tax', default='unknown', readonly=True)
    bizfinder_moms = fields.Selection(
        [('yes', 'Yes'), ('no', 'No'), ('unknown', 'Unknown')],
        string='VAT registered (moms)', default='unknown', readonly=True)

    # --- key financials (latest statement) ---------------------------------
    bizfinder_solidity_pct = fields.Float(string='Solidity %', readonly=True)
    bizfinder_growth_pct = fields.Float(string='Growth %', readonly=True)
    bizfinder_profit_margin_pct = fields.Float(string='Profit margin %', readonly=True)
    bizfinder_quick_ratio_pct = fields.Float(string='Quick ratio %', readonly=True)
    bizfinder_net_sales = fields.Float(string='Net sales (tkr)', readonly=True)
    bizfinder_account_date_to = fields.Date(string='Statement date', readonly=True)
    bizfinder_employees = fields.Char(string='Employees (bucket)', readonly=True)

    # Stored classification, written by the sync (NOT an Odoo compute) so it
    # is searchable/filterable and stable between syncs.
    bizfinder_health = fields.Selection(
        [('good', 'Good'), ('warning', 'Warning'),
         ('critical', 'Critical'), ('unknown', 'Unknown')],
        string='Financial health', default='unknown', readonly=True)

    bizfinder_monitored = fields.Boolean(string='Monitored by Bizfinder', default=False)
    bizfinder_last_sync = fields.Datetime(string='Last Bizfinder sync', readonly=True)

    bizfinder_event_count = fields.Integer(
        string='Bizfinder events', compute='_compute_bizfinder_event_count')

    def _compute_bizfinder_event_count(self):
        counts = dict(self.env['bizfinder.company.event']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        for partner in self:
            partner.bizfinder_event_count = counts.get(partner, 0)

    # ------------------------------------------------------------------ utils
    @api.model
    def _bizfinder_normalize_org(self, value) -> str:
        """Normalize an org number for the API: strip spaces and hyphens."""
        return (value or '').replace(' ', '').replace('-', '')

    def _bizfinder_org_map(self) -> dict:
        """{normalized org number: partner} for company partners in ``self``
        that carry a company_registry. Skips the rest silently (callers guard
        with their own UserError when an org number is required)."""
        org_map = {}
        for partner in self:
            if not partner.is_company:
                continue
            org = self._bizfinder_normalize_org(partner.company_registry)
            if org:
                org_map[org] = partner
        return org_map

    # ----------------------------------------------------------- health rule
    @api.model
    def _bizfinder_classify_health(self, active, f_tax, solidity, growth, quick_ratio) -> str:
        """The single place the health rule lives. Tune thresholds via the
        module constants above.

        critical: not active in the registry, F-tax revoked, or solidity
                  below SOLIDITY_CRITICAL_BELOW;
        warning:  solidity below SOLIDITY_WARNING_BELOW, growth below
                  GROWTH_WARNING_BELOW, or quick ratio below
                  QUICK_RATIO_WARNING_BELOW (each only when the value is
                  present);
        good:     otherwise (the company has been synced).
        """
        if not active or f_tax == 'no':
            return 'critical'
        if solidity is not None and solidity < SOLIDITY_CRITICAL_BELOW:
            return 'critical'
        if solidity is not None and solidity < SOLIDITY_WARNING_BELOW:
            return 'warning'
        if growth is not None and growth < GROWTH_WARNING_BELOW:
            return 'warning'
        if quick_ratio is not None and quick_ratio < QUICK_RATIO_WARNING_BELOW:
            return 'warning'
        return 'good'

    # ----------------------------------------------------------------- sync
    def bizfinder_sync_status(self):
        """Pull company-status for the partners in ``self`` and write the
        bizfinder_* fields + health classification. Free API call."""
        org_map = self._bizfinder_org_map()
        if not org_map:
            return
        client = self.env['bizfinder.client']
        orgs = list(org_map)
        now = fields.Datetime.now()
        for start in range(0, len(orgs), BATCH_SIZE):
            batch = orgs[start:start + BATCH_SIZE]
            for row in client.company_status(batch):
                partner = org_map.get(self._bizfinder_normalize_org(row.get('orgNumber')))
                if not partner:
                    _logger.warning(
                        "bizfinder: company-status returned unknown org %s; skipping",
                        row.get('orgNumber'))
                    continue
                partner.write(self._bizfinder_status_vals(row, now))

    @api.model
    def _bizfinder_status_vals(self, row: dict, sync_time) -> dict:
        status_code = int(row.get('statusCode') or 0)
        active = status_code == STATUS_CODE_ACTIVE

        def tri(value):
            if value is None:
                return 'unknown'
            return 'yes' if value else 'no'

        solidity = row.get('solidityPct')
        growth = row.get('growthPct')
        quick_ratio = row.get('quickRatioPct')
        return {
            'bizfinder_status_code': status_code,
            'bizfinder_status_text': row.get('statusText') or '',
            'bizfinder_active': active,
            'bizfinder_f_tax': tri(row.get('fTax')),
            'bizfinder_moms': tri(row.get('moms')),
            'bizfinder_solidity_pct': solidity or 0.0,
            'bizfinder_growth_pct': growth or 0.0,
            'bizfinder_profit_margin_pct': row.get('profitMarginPct') or 0.0,
            'bizfinder_quick_ratio_pct': quick_ratio or 0.0,
            'bizfinder_net_sales': row.get('netSales') or 0.0,
            'bizfinder_account_date_to': row.get('accountDateTo') or False,
            'bizfinder_employees': row.get('employees') or '',
            'bizfinder_health': self._bizfinder_classify_health(
                active, tri(row.get('fTax')), solidity, growth, quick_ratio),
            'bizfinder_last_sync': sync_time,
        }

    # -------------------------------------------------------------- actions
    def action_bizfinder_sync(self):
        """'Sync now' button on the partner form."""
        self.ensure_one()
        if not self._bizfinder_org_map():
            raise UserError(_(
                "Set the Company ID (organisation number) on this company "
                "first, then sync."))
        self.bizfinder_sync_status()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bizfinder'),
                'message': _('Company data synced from Bizfinder.'),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_bizfinder_monitor(self):
        """'Monitor with Bizfinder' list action: opt selected company partners
        with an org number into monitoring."""
        eligible = self.browse(
            [partner.id for partner in self._bizfinder_org_map().values()])
        if not eligible:
            raise UserError(_(
                "None of the selected contacts is a company with a Company ID "
                "(organisation number)."))
        eligible.write({'bizfinder_monitored': True})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Bizfinder'),
                'message': _('%s companies are now monitored by Bizfinder.', len(eligible)),
                'type': 'success',
                'sticky': False,
            },
        }

    def action_bizfinder_open_lookup(self):
        """'Fetch from Bizfinder' button: open the lookup wizard bound to
        this partner so a picked result enriches it in place."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fetch from Bizfinder'),
            'res_model': 'bizfinder.partner.lookup',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_partner_id': self.id, 'default_query': self.name or ''},
        }

    def action_bizfinder_view_events(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bizfinder Events'),
            'res_model': 'bizfinder.company.event',
            'view_mode': 'list,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'create': False},
        }
