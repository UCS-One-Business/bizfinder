# -*- coding: utf-8 -*-

import logging
from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)

# Mirrors the keys returned by /api/insight/segments. Kept here as a
# Selection so users get a typed dropdown; the values themselves come from
# the server when "Apply preset" is clicked.
PRESET_OPTIONS = [
    ('hot_growth', 'Up-and-coming SMEs'),
    ('newborns', 'Newly formed AB'),
    ('stable_profitable', 'Stable & profitable'),
    ('cash_rich_smb', 'Cash-rich SMEs'),
    ('mid_market_ab', 'Mid-market AB'),
    ('past_first_year', 'Past first year'),
    ('distressed_operating', 'Distressed but operating'),
    ('recovery_candidates', 'Recovery candidates'),
    ('it_growers', 'IT consulting growers'),
    ('construction_sme', 'Construction SMEs'),
    ('scaleups', 'Scaleups'),
    ('high_dividend', 'Dividend payers'),
    ('multi_unit_ops', 'Multi-location operations'),
    ('enterprise_candidates', 'Enterprise candidates'),
    ('equity_rich', 'Equity-rich AB'),
]

class BizfinderSearch(models.TransientModel):
    _name = 'bizfinder.search'
    _description = 'Bizfinder Search Wizard'

    @api.depends('preset_key')
    def _compute_display_name(self):
        # Override the framework-default "<model>,<id>" / "New" so the
        # breadcrumb reads as a real page name regardless of save state.
        for rec in self:
            rec.display_name = "Prospect"

    # ------------------------------------------------------------------- preset
    preset_key = fields.Selection(PRESET_OPTIONS, string='Preset segment')
    # Not readonly at the Python level: the value is populated by the
    # preset_key onchange and must survive the implicit save that runs
    # before header buttons fire. Readonly-in-view keeps users from typing.
    preset_description = fields.Text(string='Preset description')

    # ------------------------------------------------------------------- filters
    region_ids = fields.Many2many(
        'bizfinder.region',
        string='Regions',
        help="Pick one or more Swedish counties (län) to limit the search.",
    )
    industry_ids = fields.Many2many(
        'bizfinder.industry',
        'bizfinder_search_industry_rel',
        'wizard_id', 'industry_id',
        string='Industries',
        help="Curated industry shortcuts. Each expands to its SNI prefixes.",
    )
    employee_magnitude_ids = fields.Many2many(
        'bizfinder.magnitude',
        'bizfinder_search_employee_magnitude_rel',
        'wizard_id', 'magnitude_id',
        string='Employees',
        domain="[('kind', '=', 'employees')]",
        help="Coarse employee bands. Each expands to its API bucket keys.",
    )
    net_sales_magnitude_ids = fields.Many2many(
        'bizfinder.magnitude',
        'bizfinder_search_net_sales_magnitude_rel',
        'wizard_id', 'magnitude_id',
        string='Turnover',
        domain="[('kind', '=', 'net_sales')]",
        help="Coarse turnover bands. Each expands to its "
             "TURNOVER_INTERVAL keys.",
    )
    post_community_ids = fields.Many2many(
        'bizfinder.community',
        'bizfinder_search_post_community_rel',
        'wizard_id', 'community_id',
        string='Municipalities (postal)',
        help="Postal-address kommun. Start typing to filter.",
    )
    # Combined "alternative address" kommun picker — matches if either
    # the registered or the visiting community matches. Replaces the
    # separate registered/visiting pickers since users don't usually
    # care which alternative address the company filed under.
    alt_community_ids = fields.Many2many(
        'bizfinder.community',
        'bizfinder_search_alt_community_rel',
        'wizard_id', 'community_id',
        string='Kommun',
        help="Matches registered OR visiting address kommun.",
    )
    # Single ZIP prefix input that the wizard sends as a ZIP_ANY filter
    # — the API ORs it across post/registered/visiting zipcode columns
    # so users don't have to pick which address kind they care about.
    zip_prefixes = fields.Char(
        string='Postkoder',
        help="Comma-separated postnummer-prefix (1–5 digits). "
             "Matches if any of postal/registered/visiting postnummer starts with one of them.",
    )
    legal_form_ids = fields.Many2many(
        'bizfinder.legal.form',
        'bizfinder_search_legal_form_rel',
        'wizard_id', 'legal_form_id',
        string='Legal forms',
        default=lambda self: self._default_legal_form_ids(),
    )

    @api.model
    def _default_legal_form_ids(self):
        ab = self.env['bizfinder.legal.form'].search([('code', '=', 'AB')], limit=1)
        return [(6, 0, ab.ids)] if ab else False

    f_tax = fields.Selection(
        [('any', 'Any'), ('YES', 'F-tax registered'), ('NO', 'No F-tax')],
        default='any', string='F-tax')
    moms = fields.Selection(
        [('any', 'Any'), ('YES', 'VAT registered'), ('NO', 'No VAT')],
        default='any', string='VAT (Moms)')
    accountant_reservation = fields.Selection(
        [('any', 'Any'), ('YES', 'Has reservation'), ('NO', 'No reservation')],
        default='any', string='Auditor reservation')

    # Date-range filters use real Date pickers so users get a calendar
    # widget and ISO parsing for free. Each range maps to a *_DATE API
    # filter (registration_date / status_date / date_accountant_reservation).
    # ``from`` defaults to 1900-01-01 so the envelope safely covers every
    # company in the dataset; ``to`` defaults to today.
    DATE_FLOOR = '1900-01-01'

    registration_date_from = fields.Date(
        string='Registered from',
        default=lambda self: self.DATE_FLOOR,
    )
    registration_date_to = fields.Date(
        string='Registered to',
        default=lambda self: fields.Date.context_today(self),
    )
    status_date_from = fields.Date(
        string='Status changed from',
        default=lambda self: self.DATE_FLOOR,
    )
    status_date_to = fields.Date(
        string='Status changed to',
        default=lambda self: fields.Date.context_today(self),
    )
    reservation_date_from = fields.Date(
        string='Auditor reservation from',
        default=lambda self: self.DATE_FLOOR,
    )
    reservation_date_to = fields.Date(
        string='Auditor reservation to',
        default=lambda self: fields.Date.context_today(self),
    )

    # Numeric ranges pre-fill with the API bounds so the user sees the
    # full envelope and edits down, instead of staring at placeholder text.
    # Leaving an input empty drops the corresponding min/max from the
    # filter payload (see _is_set in _build_values).
    net_sales_min = fields.Char(string='Min turnover (tkr)', default='-10 000 000')
    net_sales_max = fields.Char(string='Max turnover (tkr)', default='100 000 000')
    net_operating_income_min = fields.Char(string='Min operating income (tkr)', default='-10 000 000')
    net_operating_income_max = fields.Char(string='Max operating income (tkr)', default='100 000 000')
    operating_result_min = fields.Char(string='Min operating result (tkr)', default='-10 000 000')
    operating_result_max = fields.Char(string='Max operating result (tkr)', default='100 000 000')
    profit_after_fin_min = fields.Char(string='Min profit after financials (tkr)', default='-10 000 000')
    profit_after_fin_max = fields.Char(string='Max profit after financials (tkr)', default='100 000 000')
    net_profit_loss_min = fields.Char(string='Min net profit/loss (tkr)', default='-10 000 000')
    net_profit_loss_max = fields.Char(string='Max net profit/loss (tkr)', default='100 000 000')
    growth_pct_min = fields.Char(string='Min growth %', default='-100')
    growth_pct_max = fields.Char(string='Max growth %', default='500')
    headcount_change_min = fields.Char(string='Min headcount growth %', default='-100')
    headcount_change_max = fields.Char(string='Max headcount growth %', default='500')
    solidity_pct_min = fields.Char(string='Min solidity %', default='-100')
    solidity_pct_max = fields.Char(string='Max solidity %', default='100')
    operating_margin_min = fields.Char(string='Min operating margin %', default='-100')
    operating_margin_max = fields.Char(string='Max operating margin %', default='100')
    profit_margin_min = fields.Char(string='Min profit margin %', default='-100')
    profit_margin_max = fields.Char(string='Max profit margin %', default='100')
    quick_ratio_min = fields.Char(string='Min quick ratio %', default='0')
    quick_ratio_max = fields.Char(string='Max quick ratio %', default='1000')
    turnover_per_employee_min = fields.Char(string='Min turnover/employee (tkr)', default='0')
    turnover_per_employee_max = fields.Char(string='Max turnover/employee (tkr)', default='100 000')
    employees_min = fields.Char(string='Min employees (exact)', default='0')
    employees_max = fields.Char(string='Max employees (exact)', default='100 000')
    cash_min = fields.Char(string='Min cash & bank (tkr)', default='0')
    cash_max = fields.Char(string='Max cash & bank (tkr)', default='10 000 000')
    assets_min = fields.Char(string='Min assets (tkr)', default='0')
    assets_max = fields.Char(string='Max assets (tkr)', default='100 000 000')
    equity_min = fields.Char(string='Min equity (tkr)', default='-10 000 000')
    equity_max = fields.Char(string='Max equity (tkr)', default='100 000 000')
    current_liabilities_min = fields.Char(string='Min current liabilities (tkr)', default='0')
    current_liabilities_max = fields.Char(string='Max current liabilities (tkr)', default='100 000 000')
    long_term_debts_min = fields.Char(string='Min long-term debts (tkr)', default='0')
    long_term_debts_max = fields.Char(string='Max long-term debts (tkr)', default='100 000 000')
    account_months_min = fields.Char(string='Min account months', default='0')
    account_months_max = fields.Char(string='Max account months', default='24')
    accountant_obligation = fields.Selection(
        [('any', 'Any'), ('YES', 'Auditor required'), ('NO', 'No auditor required')],
        default='any', string='Auditor obligation')
    dividend_min = fields.Char(string='Min dividend (tkr)', default='0')
    dividend_max = fields.Char(string='Max dividend (tkr)', default='100 000 000')

    # Page size for prospect previews. Hardcoded so users don't tune it
    # per-search and so billing assumptions stay stable.
    PAGE_SIZE = 200

    hit_count = fields.Integer(string='Total matches', readonly=True)
    returned_count = fields.Integer(string='Returned', readonly=True)
    duplicate_count = fields.Integer(string='Already in CRM', readonly=True)
    selected_reveal_count = fields.Integer(
        string='Selected reveals',
        compute='_compute_billing_estimate',
    )
    billing_currency = fields.Char(string='Currency', readonly=True)
    price_per_reveal = fields.Float(string='Price per reveal', readonly=True)
    estimated_reveal_total = fields.Float(
        string='Estimated cost',
        compute='_compute_billing_estimate',
    )

    result_line_ids = fields.One2many(
        'bizfinder.result.line',
        'wizard_id',
        string='Results',
    )

    @api.depends('result_line_ids.selected', 'price_per_reveal')
    def _compute_billing_estimate(self):
        for rec in self:
            selected = rec.result_line_ids.filtered(lambda line: line.selected)
            rec.selected_reveal_count = len(selected)
            rec.estimated_reveal_total = rec.selected_reveal_count * rec.price_per_reveal

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _split_csv(value: str | bool) -> list[str]:
        if not value:
            return []
        return [p.strip() for p in str(value).split(',') if p.strip()]

    @staticmethod
    def _is_set(value) -> bool:
        return value is not False and value is not None and str(value).strip() != ''

    def _range_value(self, field_name: str, value, kind: str):
        if not self._is_set(value):
            return None
        # Strip thin / regular spaces too — defaults like "10 000 000"
        # are easier to read but would otherwise blow up int()/float().
        raw = str(value).strip().replace(',', '.').replace(' ', '').replace(' ', '')
        try:
            if kind == 'range_int':
                parsed = int(raw)
            else:
                parsed = float(raw)
        except ValueError as exc:
            field = self._fields[field_name]
            raise UserError(
                _("'%(value)s' is not a valid number for %(field)s.")
                % {'value': value, 'field': field.string}
            ) from exc
        return parsed

    def _append_range(self, values: list[dict], key: str, lo_field: str, hi_field: str, kind: str):
        lo = self._range_value(lo_field, self[lo_field], kind)
        hi = self._range_value(hi_field, self[hi_field], kind)
        if lo is None and hi is None:
            return
        r = {}
        if lo is not None:
            r['min'] = lo
        if hi is not None:
            r['max'] = hi
        values.append({'filterCategory': key, 'SelectRange': r})

    def _build_values(self) -> list[dict]:
        values: list[dict] = []
        if self.region_ids:
            values.append({'filterCategory': 'POST_REGION_CODE',
                           'SelectOption': self.region_ids.mapped('code')})
        if self.post_community_ids:
            values.append({'filterCategory': 'POST_KOMMUNKOD',
                           'SelectOption': self.post_community_ids.mapped('kommunkod')})
        if self.alt_community_ids:
            values.append({'filterCategory': 'ALT_KOMMUNKOD',
                           'SelectOption': self.alt_community_ids.mapped('kommunkod')})
        if prefixes := self._split_csv(self.zip_prefixes):
            values.append({'filterCategory': 'ZIP_ANY', 'SelectOption': prefixes})
        if snis := self.industry_ids.expand_prefixes():
            snis = list(dict.fromkeys(snis))
            values.append({'filterCategory': 'SNI_PREFIX', 'SelectOption': snis})
        if self.legal_form_ids:
            values.append({'filterCategory': 'LEGALGROUP_CODE',
                           'SelectOption': self.legal_form_ids.mapped('code')})
        if turnover_keys := list(dict.fromkeys(self.net_sales_magnitude_ids.expand_keys())):
            values.append({'filterCategory': 'TURNOVER_INTERVAL',
                           'SelectOption': turnover_keys})
        if employee_keys := list(dict.fromkeys(self.employee_magnitude_ids.expand_keys())):
            values.append({'filterCategory': 'NBR_EMPLOYEES_INTERVAL',
                           'SelectOption': employee_keys})
        if self.f_tax and self.f_tax != 'any':
            values.append({'filterCategory': 'F_TAX', 'SelectOption': [self.f_tax]})
        if self.moms and self.moms != 'any':
            values.append({'filterCategory': 'MOMS', 'SelectOption': [self.moms]})
        if self.accountant_reservation and self.accountant_reservation != 'any':
            values.append({'filterCategory': 'ACCOUNTANT_RESERVATION',
                           'SelectOption': [self.accountant_reservation]})
        if self.accountant_obligation and self.accountant_obligation != 'any':
            values.append({'filterCategory': 'ACCOUNTANT_OBLIGATION',
                           'SelectOption': [self.accountant_obligation]})
        for key, lo_f, hi_f in [
            ('REGISTERED_DATE', 'registration_date_from', 'registration_date_to'),
            ('STATUS_CHANGED_DATE', 'status_date_from', 'status_date_to'),
            ('RESERVATION_DATE', 'reservation_date_from', 'reservation_date_to'),
        ]:
            lo, hi = self[lo_f], self[hi_f]
            if not lo and not hi:
                continue
            r = {}
            if lo:
                r['min'] = fields.Date.to_string(lo)
            if hi:
                r['max'] = fields.Date.to_string(hi)
            values.append({'filterCategory': key, 'SelectRange': r})
        for key, lo, hi, kind in [
            ('NET_SALES', 'net_sales_min', 'net_sales_max', 'range_float'),
            ('NET_OPERATING_INCOME', 'net_operating_income_min',
             'net_operating_income_max', 'range_float'),
            ('OPERATING_RESULT', 'operating_result_min', 'operating_result_max', 'range_float'),
            ('PROFIT_LOSS_AFTER_FIN', 'profit_after_fin_min', 'profit_after_fin_max', 'range_float'),
            ('NET_PROFIT_LOSS', 'net_profit_loss_min', 'net_profit_loss_max', 'range_float'),
            ('GROWTH_PCT', 'growth_pct_min', 'growth_pct_max', 'range_float'),
            ('HEADCOUNT_CHANGE_PCT', 'headcount_change_min', 'headcount_change_max', 'range_float'),
            ('SOLIDITY_PCT', 'solidity_pct_min', 'solidity_pct_max', 'range_float'),
            ('OPERATING_MARGIN_PCT', 'operating_margin_min', 'operating_margin_max', 'range_float'),
            ('PROFIT_MARGIN_PCT', 'profit_margin_min', 'profit_margin_max', 'range_float'),
            ('QUICK_RATIO_PCT', 'quick_ratio_min', 'quick_ratio_max', 'range_float'),
            ('TURNOVER_PER_EMPLOYEE', 'turnover_per_employee_min',
             'turnover_per_employee_max', 'range_float'),
            ('EMPLOYEES_EXACT', 'employees_min', 'employees_max', 'range_int'),
            ('CASH_AT_BANK', 'cash_min', 'cash_max', 'range_float'),
            ('TOTAL_ASSETS', 'assets_min', 'assets_max', 'range_float'),
            ('TOTAL_EQUITY', 'equity_min', 'equity_max', 'range_float'),
            ('CURRENT_LIABILITIES', 'current_liabilities_min',
             'current_liabilities_max', 'range_float'),
            ('LONG_TERM_DEBTS', 'long_term_debts_min', 'long_term_debts_max', 'range_float'),
            ('ACCOUNT_MONTHS', 'account_months_min', 'account_months_max', 'range_int'),
            ('DIVIDEND', 'dividend_min', 'dividend_max', 'range_float'),
        ]:
            self._append_range(values, key, lo, hi, kind)
        return values

    # --------------------------------------------------------------- preset

    _filter_to_field_map: dict = {
        'POST_REGION_CODE': ('region_ids', 'm2m_region'),
        'POST_KOMMUNKOD': ('post_community_ids', 'm2m_community'),
        # Old per-address picker preset entries now funnel into the
        # unified alt_community_ids; VISITING_REGION_CODE is dropped
        # since no current preset uses it.
        'REGISTERED_KOMMUNKOD': ('alt_community_ids', 'm2m_community'),
        'VISITING_KOMMUNKOD': ('alt_community_ids', 'm2m_community'),
        'ALT_KOMMUNKOD': ('alt_community_ids', 'm2m_community'),
        # All three legacy ZIP prefix categories funnel into the single
        # zip_prefixes field, so a preset that targeted a specific
        # address kind still populates the consolidated input.
        'POST_ZIP_PREFIX': ('zip_prefixes', 'csv'),
        'REGISTERED_ZIP_PREFIX': ('zip_prefixes', 'csv'),
        'VISITING_ZIP_PREFIX': ('zip_prefixes', 'csv'),
        'ZIP_ANY': ('zip_prefixes', 'csv'),
        'SNI_PREFIX': ('industry_ids', 'm2m_industry_by_sni'),
        'LEGALGROUP_CODE': ('legal_form_ids', 'm2m_legal_form'),
        # Magnitudes are now the single tag picker for both buckets;
        # presets that reference raw API bucket keys are resolved by
        # matching against magnitude.bucket_keys CSV membership.
        'TURNOVER_INTERVAL': ('net_sales_magnitude_ids', 'm2m_magnitude_by_key'),
        'NBR_EMPLOYEES_INTERVAL': ('employee_magnitude_ids', 'm2m_magnitude_by_key'),
        'F_TAX': ('f_tax', 'select'),
        'MOMS': ('moms', 'select'),
        'ACCOUNTANT_RESERVATION': ('accountant_reservation', 'select'),
        'ACCOUNTANT_OBLIGATION': ('accountant_obligation', 'select'),
        # Old API filter categories that use "months ago" semantics map
        # to the new Date pickers via a months-to-date conversion when
        # a preset references them.
        'REGISTERED_WITHIN_MONTHS': (
            ('registration_date_from', 'registration_date_to'), 'range_months_to_date'),
        'REGISTERED_DATE': (
            ('registration_date_from', 'registration_date_to'), 'range_date'),
        'STATUS_CHANGED_WITHIN_MONTHS': (
            ('status_date_from', 'status_date_to'), 'range_months_to_date'),
        'STATUS_CHANGED_DATE': (
            ('status_date_from', 'status_date_to'), 'range_date'),
        'ACCOUNTANT_RESERVATION_WITHIN_MONTHS': (
            ('reservation_date_from', 'reservation_date_to'), 'range_months_to_date'),
        'RESERVATION_DATE': (
            ('reservation_date_from', 'reservation_date_to'), 'range_date'),
        'NET_SALES': (('net_sales_min', 'net_sales_max'), 'range_float'),
        'NET_OPERATING_INCOME': (
            ('net_operating_income_min', 'net_operating_income_max'), 'range_float'),
        'OPERATING_RESULT': (('operating_result_min', 'operating_result_max'), 'range_float'),
        'PROFIT_LOSS_AFTER_FIN': (('profit_after_fin_min', 'profit_after_fin_max'), 'range_float'),
        'NET_PROFIT_LOSS': (('net_profit_loss_min', 'net_profit_loss_max'), 'range_float'),
        'GROWTH_PCT': (('growth_pct_min', 'growth_pct_max'), 'range_float'),
        'HEADCOUNT_CHANGE_PCT': (('headcount_change_min', 'headcount_change_max'), 'range_float'),
        'SOLIDITY_PCT': (('solidity_pct_min', 'solidity_pct_max'), 'range_float'),
        'OPERATING_MARGIN_PCT': (('operating_margin_min', 'operating_margin_max'), 'range_float'),
        'PROFIT_MARGIN_PCT': (('profit_margin_min', 'profit_margin_max'), 'range_float'),
        'QUICK_RATIO_PCT': (('quick_ratio_min', 'quick_ratio_max'), 'range_float'),
        'TURNOVER_PER_EMPLOYEE': (
            ('turnover_per_employee_min', 'turnover_per_employee_max'), 'range_float'),
        'EMPLOYEES_EXACT': (('employees_min', 'employees_max'), 'range_int'),
        'CASH_AT_BANK': (('cash_min', 'cash_max'), 'range_float'),
        'TOTAL_ASSETS': (('assets_min', 'assets_max'), 'range_float'),
        'TOTAL_EQUITY': (('equity_min', 'equity_max'), 'range_float'),
        'CURRENT_LIABILITIES': (
            ('current_liabilities_min', 'current_liabilities_max'), 'range_float'),
        'LONG_TERM_DEBTS': (('long_term_debts_min', 'long_term_debts_max'), 'range_float'),
        'ACCOUNT_MONTHS': (('account_months_min', 'account_months_max'), 'range_int'),
        'DIVIDEND': (('dividend_min', 'dividend_max'), 'range_float'),
    }

    _M2M_KINDS = frozenset({
        'm2m_region', 'm2m_community', 'm2m_industry_by_sni',
        'm2m_legal_form', 'm2m_magnitude_by_key',
    })

    @classmethod
    def _zero(cls, kind: str):
        if kind in cls._M2M_KINDS:
            return [(5, 0, 0)]
        return {
            'csv': '',
            'select': 'any',
            'range_int': '',
            'range_float': '',
            # Date-typed targets clear to False so the date widget reads
            # as empty rather than today's date.
            'range_date': False,
            'range_months_to_date': False,
        }[kind]

    def _reset_filters(self) -> dict:
        """Return a vals dict that clears every server-mapped filter."""
        vals: dict = {}
        for filter_cat, (target, kind) in self._filter_to_field_map.items():
            zero = self._zero(kind)
            if isinstance(target, tuple):
                for f in target:
                    vals[f] = zero
            else:
                vals[target] = zero
        # Clear local-only shortcut fields too, so a preset switch wipes
        # the previous preset's auto-fill cleanly.
        vals['industry_ids'] = [(5, 0, 0)]
        vals['employee_magnitude_ids'] = [(5, 0, 0)]
        vals['net_sales_magnitude_ids'] = [(5, 0, 0)]
        return vals

    @api.model
    def action_open_search(self) -> dict:
        """Entry point used by the CRM menu. Creates a fresh wizard record
        and returns a full-page form action targeted at the current window."""
        if not self.env.user.has_group('sales_team.group_sale_salesman'):
            raise AccessError(_("Only CRM sales users can access Bizfinder."))
        rec = self.create({})
        return {
            'type': 'ir.actions.act_window',
            'name': 'Prospect Search',
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }


    def _resolve_preset_vals(self) -> dict:
        """Build the field-write vals for the currently selected preset."""
        client = self.env['bizfinder.client']
        segments = client.get_segments()
        seg = next((s for s in segments if s.get('key') == self.preset_key), None)
        if seg is None:
            raise UserError(_("Preset %s is not known to the API.") % self.preset_key)

        vals = self._reset_filters()
        vals['preset_description'] = seg.get('description') or ''

        for f in seg.get('filters', []):
            cat = f.get('filterCategory')
            entry = self._filter_to_field_map.get(cat)
            if not entry:
                _logger.warning("preset references unknown filter %s", cat)
                continue
            target, kind = entry
            if kind == 'csv':
                opts = f.get('SelectOption') or []
                vals[target] = ','.join(str(o) for o in opts)
            elif kind == 'm2m_region':
                opts = f.get('SelectOption') or []
                if not opts:
                    continue
                codes = [int(o) for o in opts]
                regions = self.env['bizfinder.region'].search([('code', 'in', codes)])
                vals[target] = [(6, 0, regions.ids)]
            elif kind == 'm2m_community':
                opts = f.get('SelectOption') or []
                if not opts:
                    continue
                codes = [int(o) for o in opts]
                comms = self.env['bizfinder.community'].search([('kommunkod', 'in', codes)])
                vals[target] = [(6, 0, comms.ids)]
            elif kind == 'm2m_industry_by_sni':
                # Preset gave us raw SNI prefixes; resolve them to the
                # curated industry rows whose sni_prefixes CSV contains
                # any of them. Exact-match on prefix string.
                opts = [str(o) for o in (f.get('SelectOption') or []) if str(o)]
                if not opts:
                    continue
                industries = self.env['bizfinder.industry'].search([])
                wanted = set(opts)
                matched = industries.filtered(
                    lambda i: wanted.intersection(set(i.expand_prefixes()))
                )
                vals[target] = [(6, 0, matched.ids)]
            elif kind == 'm2m_legal_form':
                opts = f.get('SelectOption') or []
                if not opts:
                    continue
                codes = [str(o) for o in opts]
                lfs = self.env['bizfinder.legal.form'].search([('code', 'in', codes)])
                vals[target] = [(6, 0, lfs.ids)]
            elif kind == 'm2m_magnitude_by_key':
                # Preset gives us raw API bucket keys; resolve to the
                # magnitude rows whose bucket_keys CSV contains any of
                # them. Field target tells us which magnitude kind.
                opts = [str(o) for o in (f.get('SelectOption') or []) if str(o)]
                if not opts:
                    continue
                mag_kind = ('employees' if target == 'employee_magnitude_ids'
                            else 'net_sales')
                magnitudes = self.env['bizfinder.magnitude'].search(
                    [('kind', '=', mag_kind)])
                wanted = set(opts)
                matched = magnitudes.filtered(
                    lambda m: wanted.intersection(set(m.expand_keys()))
                )
                vals[target] = [(6, 0, matched.ids)]
            elif kind == 'select':
                opts = f.get('SelectOption') or []
                vals[target] = str(opts[0]) if opts else 'any'
            elif kind in ('range_int', 'range_float'):
                rng = f.get('SelectRange') or {}
                lo_field, hi_field = target
                if rng.get('min') is not None:
                    vals[lo_field] = str(int(rng['min']) if kind == 'range_int' else rng['min'])
                if rng.get('max') is not None:
                    vals[hi_field] = str(int(rng['max']) if kind == 'range_int' else rng['max'])
            elif kind == 'range_date':
                # Preset gave ISO date strings; pass them straight to the
                # Date target fields.
                rng = f.get('SelectRange') or {}
                lo_field, hi_field = target
                if rng.get('min'):
                    vals[lo_field] = rng['min']
                if rng.get('max'):
                    vals[hi_field] = rng['max']
            elif kind == 'range_months_to_date':
                # Legacy *_WITHIN_MONTHS preset values mean "this many
                # months ago"; convert to absolute dates so the new Date
                # pickers light up correctly.
                from dateutil.relativedelta import relativedelta
                today = fields.Date.context_today(self)
                rng = f.get('SelectRange') or {}
                lo_field, hi_field = target
                # max=N months -> "no older than N months ago" -> date_from
                if rng.get('max') is not None:
                    vals[lo_field] = today - relativedelta(months=int(rng['max']))
                # min=N months -> "at least N months ago" -> date_to
                if rng.get('min') is not None:
                    vals[hi_field] = today - relativedelta(months=int(rng['min']))
        return vals

    @api.onchange('preset_key')
    def _onchange_preset_key(self):
        """Auto-apply preset filters as soon as the user picks one."""
        if not self.preset_key:
            self.preset_description = False
            return
        vals = self._resolve_preset_vals()
        # Onchange writes to the in-memory record; no need to call write().
        for fname, value in vals.items():
            self[fname] = value

    # ----------------------------------------------------------------- search

    def action_search(self):
        self.ensure_one()
        client = self.env['bizfinder.client']
        self._refresh_billing_pricing(client)
        values = self._build_values()
        # Fetch the true total alongside the result page so the user sees
        # both "what was returned" and "what's available".
        total = client.preview(values)
        rows = client.search(values, skip=0, take=self.PAGE_SIZE)

        # Dedupe against companies that already exist as crm.lead records
        # in this database. The dedup key is `company_organisation_number`
        # which this module writes when leads are created from the wizard.
        org_numbers = [r.get('organisationNumber') for r in rows if r.get('organisationNumber')]
        existing = set()
        if org_numbers:
            existing = set(self.env['crm.lead'].sudo().search([
                ('company_organisation_number', 'in', org_numbers),
            ]).mapped('company_organisation_number'))
        before = len(rows)
        rows = [r for r in rows if r.get('organisationNumber') not in existing]
        duplicates = before - len(rows)

        self.result_line_ids.unlink()
        Line = self.env['bizfinder.result.line']
        Line.create([{
            'wizard_id': self.id,
            'name': r.get('name') or '(unknown)',
            'organisation_number': r.get('organisationNumber') or '',
            'vat_number': r.get('vatNumber') or '',
            'phone': r.get('phone') or '',
            'fax': r.get('fax') or '',
            'address': r.get('address') or '',
            'post_code': r.get('postCode') or '',
            'city': r.get('city') or '',
            'post_community': r.get('postCommunity') or '',
            'visiting_address': r.get('visitingAddress') or '',
            'visiting_post_code': r.get('visitingPostCode') or '',
            'visiting_city': r.get('visitingCity') or '',
            'visiting_community': r.get('visitingCommunity') or '',
            'description': r.get('description') or '',
            'employees': r.get('employees') or '',
            'turn_over': r.get('turnOver') or '',
            'legal_entity': r.get('legalEntityText') or r.get('legalEntity') or '',
            'number_of_units': r.get('numberOfUnits') or 0,
            'net_sales': r.get('netSales') or 0.0,
            'operating_result': r.get('operatingResult') or 0.0,
            'net_profit_loss': r.get('netProfitLoss') or 0.0,
            'growth_pct': r.get('growthPct') or 0.0,
            'headcount_change_pct': r.get('headcountChangePct') or 0.0,
            'solidity_pct': r.get('solidityPct') or 0.0,
            'operating_margin_pct': r.get('operatingMarginPct') or 0.0,
            'profit_margin_pct': r.get('profitMarginPct') or 0.0,
            'quick_ratio_pct': r.get('quickRatioPct') or 0.0,
            'cash_at_bank': r.get('cashAtBank') or 0.0,
            'total_assets': r.get('totalAssets') or 0.0,
            'total_equity': r.get('totalEquity') or 0.0,
            'account_date_to': r.get('accountDateTo') or False,
            'account_months': r.get('accountMonths') or 0,
            'accountant_obligation': r.get('accountantObligation') or False,
            'director_name': r.get('directorName') or '',
            'director_role': r.get('directorRole') or '',
            'registration_date': r.get('registrationDate') or False,
            'company_formed_date': r.get('companyFormedDate') or False,
            'status_date': r.get('statusDate') or False,
        } for r in rows])
        self.hit_count = total
        self.returned_count = len(rows)
        self.duplicate_count = duplicates

    def _refresh_billing_pricing(self, client=None):
        client = client or self.env['bizfinder.client']
        pricing = client.get_billing_pricing()
        self.price_per_reveal = float(pricing.get('pricePerReveal') or 0.0)
        self.billing_currency = pricing.get('currency') or ''

    @staticmethod
    def _format_notes(data: dict) -> str:
        """Render every field of a revealed prospect into the lead's
        description (notes). `data` is the JSON dict returned by the
        /api/insight/reveal endpoint, not a result_line record, since
        the result_line carries redacted data."""
        def kv(label, value):
            if not value and value != 0:
                return ""
            return f"<li><b>{escape(label)}:</b> {escape(str(value))}</li>"

        dn = data.get('directorName') or ''
        dr = data.get('directorRole') or ''
        director = f"{dn} ({dr})" if dn and dr else (dn or '')

        postal_parts = []
        if data.get('address'):
            postal_parts.append(data['address'])
        zc = (data.get('postCode') or '').strip()
        ct = (data.get('city') or '').strip()
        if zc or ct:
            postal_parts.append(f"{zc} {ct}".strip())
        postal = ", ".join(postal_parts)

        visiting_parts = []
        if data.get('visitingAddress'):
            visiting_parts.append(data['visitingAddress'])
        vz = (data.get('visitingPostCode') or '').strip()
        if data.get('visitingCity'):
            visiting_parts.append(f"{vz} {data['visitingCity']}".strip())
        visiting = ", ".join(visiting_parts)

        growth_v = data.get('growthPct')
        headcount_v = data.get('headcountChangePct')
        solidity_v = data.get('solidityPct')
        growth = f"{growth_v:.1f}%" if isinstance(growth_v, (int, float)) and growth_v else ""
        headcount = (
            f"{headcount_v:.1f}%"
            if isinstance(headcount_v, (int, float)) and headcount_v else ""
        )
        solidity = f"{solidity_v:.1f}%" if isinstance(solidity_v, (int, float)) and solidity_v else ""

        registered_parts = []
        if data.get('registeredAddress'):
            registered_parts.append(data['registeredAddress'])
        rz = (data.get('registeredPostCode') or '').strip()
        rc = (data.get('registeredCity') or '').strip()
        if rz or rc:
            registered_parts.append(f"{rz} {rc}".strip())
        registered = ", ".join(registered_parts)

        sections = []
        company = "".join(filter(None, [
            kv("Organisation number", data.get('organisationNumber')),
            kv("VAT number", data.get('vatNumber')),
            kv("Industry (SNI)", data.get('description')),
            kv("Legal form", data.get('legalEntityText') or data.get('legalEntity')),
            kv("Municipality", data.get('postCommunity')),
            kv("Company formed", data.get('companyFormedDate')),
            kv("Registered", data.get('registrationDate')),
            kv("Status changed", data.get('statusDate')),
            kv("Units", data.get('numberOfUnits')),
        ]))
        if company:
            sections.append(f"<p><b>Company</b></p><ul>{company}</ul>")

        contact = "".join(filter(None, [
            kv("Top director", director),
            kv("Phone", data.get('phone')),
            kv("Fax", data.get('fax')),
        ]))
        if contact:
            sections.append(f"<p><b>Contact</b></p><ul>{contact}</ul>")

        addr = "".join(filter(None, [
            kv("Postal", postal),
            kv("Visiting", visiting),
            kv("Registered", registered),
        ]))
        if addr:
            sections.append(f"<p><b>Address</b></p><ul>{addr}</ul>")

        financials = "".join(filter(None, [
            kv("Employees", data.get('employees')),
            kv("Turnover", data.get('turnOver')),
            kv("Latest statement", data.get('accountDateTo')),
            kv("Account months", data.get('accountMonths')),
            kv("Net sales (tkr)", data.get('netSales')),
            kv("Operating income (tkr)", data.get('netOperatingIncome')),
            kv("Operating result (tkr)", data.get('operatingResult')),
            kv("Profit after financials (tkr)", data.get('profitLossAfterFin')),
            kv("Net profit/loss (tkr)", data.get('netProfitLoss')),
            kv("Growth", growth),
            kv("Headcount growth", headcount),
            kv("Solidity", solidity),
            kv("Operating margin %", data.get('operatingMarginPct')),
            kv("Profit margin %", data.get('profitMarginPct')),
            kv("Quick ratio %", data.get('quickRatioPct')),
            kv("Turnover per employee (tkr)", data.get('turnoverPerEmployee')),
            kv("Cash and bank (tkr)", data.get('cashAtBank')),
            kv("Total assets (tkr)", data.get('totalAssets')),
            kv("Total equity (tkr)", data.get('totalEquity')),
            kv("Current liabilities (tkr)", data.get('currentLiabilities')),
            kv("Long-term debts (tkr)", data.get('longTermDebts')),
            kv("Dividend (tkr)", data.get('dividend')),
            kv("Auditor obligation", data.get('accountantObligation')),
        ]))
        if financials:
            sections.append(f"<p><b>Financials (latest year)</b></p><ul>{financials}</ul>")

        if sections:
            sections.insert(0, "<p><i>Imported from Creditsafe via Bizfinder.</i></p>")
        return "".join(sections)

    def action_create_leads(self):
        self.ensure_one()
        selected = self.result_line_ids.filtered(lambda l: l.selected)
        if not selected:
            raise UserError(_("Select at least one prospect first."))

        org_numbers = [l.organisation_number for l in selected if l.organisation_number]
        existing = set()
        if org_numbers:
            existing = set(self.env['crm.lead'].sudo().search([
                ('company_organisation_number', 'in', org_numbers),
            ]).mapped('company_organisation_number'))
        if existing:
            selected = selected.filtered(lambda l: l.organisation_number not in existing)
            org_numbers = [l.organisation_number for l in selected if l.organisation_number]
        if not selected:
            raise UserError(_("All selected prospects already exist in CRM."))

        client = self.env['bizfinder.client']
        self._refresh_billing_pricing(client)
        if not self.env.context.get('bizfinder_billing_confirmed'):
            confirm = self.env['bizfinder.reveal.confirm'].create({
                'wizard_id': self.id,
                'reveal_count': len(org_numbers),
                'price_per_reveal': self.price_per_reveal,
                'currency': self.billing_currency,
            })
            return {
                'type': 'ir.actions.act_window',
                'name': _('Confirm billable reveals'),
                'res_model': 'bizfinder.reveal.confirm',
                'res_id': confirm.id,
                'view_mode': 'form',
                'views': [(False, 'form')],
                'target': 'new',
            }

        # Reveal full contact info server-side. This is the metered call —
        # one reveal_log row gets written per org_number on the API side.
        revealed = {r.get('organisationNumber'): r for r in client.reveal(org_numbers)}

        Lead = self.env['crm.lead']
        created = Lead
        for line in selected:
            if line.organisation_number and Lead.sudo().search_count([
                ('company_organisation_number', '=', line.organisation_number),
            ], limit=1):
                _logger.warning(
                    "org %s already exists in CRM before create; skipping",
                    line.organisation_number,
                )
                continue
            data = revealed.get(line.organisation_number)
            if not data:
                # Reveal server-side could legitimately drop an org if it's
                # been removed since the search ran. Skip rather than create
                # a partial lead.
                _logger.warning("reveal returned no data for org %s; skipping",
                                line.organisation_number)
                continue
            created |= Lead.create({
                'name': data.get('name') or line.name,
                'partner_name': data.get('name') or line.name,
                'phone': data.get('phone') or False,
                'street': data.get('address') or False,
                'zip': data.get('postCode') or False,
                'city': data.get('city') or False,
                'description': self._format_notes(data) or False,
                'company_vat_number': data.get('vatNumber') or False,
                'company_organisation_number': data.get('organisationNumber') or False,
                'company_employees': data.get('employees') or False,
                'company_turnover': data.get('turnOver') or False,
                'company_legal_entity': (
                    data.get('legalEntityText') or data.get('legalEntity') or False
                ),
                'company_director_name': data.get('directorName') or False,
                'company_director_role': data.get('directorRole') or False,
                'company_visiting_address': data.get('visitingAddress') or False,
                'company_visiting_city': data.get('visitingCity') or False,
                'company_post_community': data.get('postCommunity') or False,
                'company_registered_address': data.get('registeredAddress') or False,
                'company_registered_city': data.get('registeredCity') or False,
                'company_visiting_post_code': data.get('visitingPostCode') or False,
                'company_visiting_community': data.get('visitingCommunity') or False,
                'company_number_of_units': data.get('numberOfUnits') or 0,
                'company_net_sales': data.get('netSales') or 0.0,
                'company_operating_result': data.get('operatingResult') or 0.0,
                'company_net_profit_loss': data.get('netProfitLoss') or 0.0,
                'company_account_date_to': data.get('accountDateTo') or False,
                'company_solidity_pct': data.get('solidityPct') or 0.0,
                'company_growth_pct': data.get('growthPct') or 0.0,
            })
        if not created:
            raise UserError(_("No leads were created. The selected prospects could not be revealed."))

        # Land on a focused CRM list containing only the records created by
        # this action, so the user can review and assign them immediately.
        action = self.env['ir.actions.act_window']._for_xml_id('crm.crm_lead_all_leads')
        action['name'] = _('Created Bizfinder Leads')
        action['domain'] = [('id', 'in', created.ids)]
        action['context'] = {
            'create': False,
            'search_default_assigned_to_me': 0,
        }
        return action


class BizfinderResultLine(models.TransientModel):
    _name = 'bizfinder.result.line'
    _description = 'Bizfinder Result Line'
    _order = 'growth_pct desc, name'

    wizard_id = fields.Many2one('bizfinder.search', required=True, ondelete='cascade')
    selected = fields.Boolean(string='Select')
    name = fields.Char(string='Company', readonly=True)
    organisation_number = fields.Char(string='Org no.', readonly=True)
    vat_number = fields.Char(string='VAT', readonly=True)
    phone = fields.Char(readonly=True)
    fax = fields.Char(readonly=True)
    address = fields.Char(readonly=True)
    post_code = fields.Char(readonly=True)
    city = fields.Char(readonly=True)
    post_community = fields.Char(string='Municipality', readonly=True)
    visiting_address = fields.Char(string='Visiting addr.', readonly=True)
    visiting_post_code = fields.Char(string='Visiting ZIP', readonly=True)
    visiting_city = fields.Char(string='Visiting city', readonly=True)
    visiting_community = fields.Char(string='Visiting municipality', readonly=True)
    description = fields.Char(string='SNI', readonly=True)
    employees = fields.Char(readonly=True)
    turn_over = fields.Char(string='Turnover', readonly=True)
    legal_entity = fields.Char(string='Form', readonly=True)
    number_of_units = fields.Integer(string='Units', readonly=True)
    net_sales = fields.Float(string='Net sales', readonly=True)
    operating_result = fields.Float(string='Operating result', readonly=True)
    net_profit_loss = fields.Float(string='Net profit/loss', readonly=True)
    growth_pct = fields.Float(string='Growth %', readonly=True)
    headcount_change_pct = fields.Float(string='Headcount growth %', readonly=True)
    solidity_pct = fields.Float(string='Solidity %', readonly=True)
    operating_margin_pct = fields.Float(string='Operating margin %', readonly=True)
    profit_margin_pct = fields.Float(string='Profit margin %', readonly=True)
    quick_ratio_pct = fields.Float(string='Quick ratio %', readonly=True)
    cash_at_bank = fields.Float(string='Cash and bank', readonly=True)
    total_assets = fields.Float(string='Assets', readonly=True)
    total_equity = fields.Float(string='Equity', readonly=True)
    account_date_to = fields.Date(string='Statement date', readonly=True)
    account_months = fields.Integer(string='Account months', readonly=True)
    accountant_obligation = fields.Boolean(string='Auditor required', readonly=True)
    director_name = fields.Char(string='Top director', readonly=True)
    director_role = fields.Char(string='Director role', readonly=True)
    registration_date = fields.Date(string='Registered', readonly=True)
    company_formed_date = fields.Date(string='Formed', readonly=True)
    status_date = fields.Date(string='Status date', readonly=True)


class BizfinderRevealConfirm(models.TransientModel):
    _name = 'bizfinder.reveal.confirm'
    _description = 'Bizfinder Reveal Billing Confirmation'

    wizard_id = fields.Many2one('bizfinder.search', required=True, ondelete='cascade')
    reveal_count = fields.Integer(string='Billable reveals', readonly=True)
    price_per_reveal = fields.Float(string='Price per reveal', readonly=True)
    currency = fields.Char(readonly=True)
    estimated_total = fields.Float(
        string='Estimated total',
        compute='_compute_estimated_total',
    )

    @api.depends('reveal_count', 'price_per_reveal')
    def _compute_estimated_total(self):
        for rec in self:
            rec.estimated_total = rec.reveal_count * rec.price_per_reveal

    def action_confirm(self):
        self.ensure_one()
        return self.wizard_id.with_context(bizfinder_billing_confirmed=True).action_create_leads()
