# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BizfinderFilterMixin(models.AbstractModel):
    """Shared company-search filter set + filter logic.

    Both the search wizard (bizfinder.search) and saved presets
    (bizfinder.preset) describe the same set of company filters, so the scalar
    filter fields and all the encode/decode logic live here and are reused by
    both. The Many2many filter fields are NOT defined here: two of them point
    at the same comodel (community / magnitude), so they need distinct relation
    tables per concrete model — each model declares them with its own relation
    name. The methods below reference those m2m field names, which exist on
    every concrete model that uses this mixin.
    """
    _name = 'bizfinder.filter.mixin'
    _description = 'Bizfinder Filter Mixin'

    # ``from`` defaults to 1900-01-01 so the envelope safely covers every
    # company in the dataset; ``to`` defaults to today.
    DATE_FLOOR = '1900-01-01'

    @api.model
    def _default_legal_form_ids(self):
        ab = self.env['bizfinder.legal.form'].search([('code', '=', 'AB')], limit=1)
        return [(6, 0, ab.ids)] if ab else False

    zip_prefixes = fields.Char(
        string='Postkoder',
        help="Comma-separated postnummer-prefix (1–5 digits). "
             "Matches if any of postal/registered/visiting postnummer starts with one of them.",
    )
    f_tax = fields.Selection(
        [('any', 'Any'), ('YES', 'F-tax registered'), ('NO', 'No F-tax')],
        default='any', string='F-tax')
    moms = fields.Selection(
        [('any', 'Any'), ('YES', 'VAT registered'), ('NO', 'No VAT')],
        default='any', string='VAT (Moms)')
    accountant_reservation = fields.Selection(
        [('any', 'Any'), ('YES', 'Has reservation'), ('NO', 'No reservation')],
        default='any', string='Auditor reservation')
    accountant_obligation = fields.Selection(
        [('any', 'Any'), ('YES', 'Auditor required'), ('NO', 'No auditor required')],
        default='any', string='Auditor obligation')

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

    # Trimmed to the handful of ranges sales actually filters on. Leaving an
    # input empty drops the corresponding min/max from the filter payload.
    net_sales_min = fields.Char(string='Min turnover (tkr)', default='-10 000 000')
    net_sales_max = fields.Char(string='Max turnover (tkr)', default='100 000 000')
    net_profit_loss_min = fields.Char(string='Min net profit/loss (tkr)', default='-10 000 000')
    net_profit_loss_max = fields.Char(string='Max net profit/loss (tkr)', default='100 000 000')
    growth_pct_min = fields.Char(string='Min growth %', default='-100')
    growth_pct_max = fields.Char(string='Max growth %', default='500')
    solidity_pct_min = fields.Char(string='Min solidity %', default='-100')
    solidity_pct_max = fields.Char(string='Max solidity %', default='100')
    employees_min = fields.Char(string='Min employees (exact)', default='0')
    employees_max = fields.Char(string='Max employees (exact)', default='100 000')

    # --------------------------------------------------------------- helpers

    @staticmethod
    def _split_csv(value) -> list:
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
        raw = str(value).strip().replace(',', '.').replace(' ', '').replace(' ', '')
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

    def _append_range(self, values: list, key: str, lo_field: str, hi_field: str, kind: str):
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

    def _build_values(self) -> list:
        """Encode the current filter fields into the API's filter payload."""
        self.ensure_one()
        values: list = []
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
            ('NET_PROFIT_LOSS', 'net_profit_loss_min', 'net_profit_loss_max', 'range_float'),
            ('GROWTH_PCT', 'growth_pct_min', 'growth_pct_max', 'range_float'),
            ('SOLIDITY_PCT', 'solidity_pct_min', 'solidity_pct_max', 'range_float'),
            ('EMPLOYEES_EXACT', 'employees_min', 'employees_max', 'range_int'),
        ]:
            self._append_range(values, key, lo, hi, kind)
        return values

    # ----------------------------------------------------------------- decode

    _filter_to_field_map: dict = {
        'POST_REGION_CODE': ('region_ids', 'm2m_region'),
        'POST_KOMMUNKOD': ('post_community_ids', 'm2m_community'),
        'REGISTERED_KOMMUNKOD': ('alt_community_ids', 'm2m_community'),
        'VISITING_KOMMUNKOD': ('alt_community_ids', 'm2m_community'),
        'ALT_KOMMUNKOD': ('alt_community_ids', 'm2m_community'),
        'POST_ZIP_PREFIX': ('zip_prefixes', 'csv'),
        'REGISTERED_ZIP_PREFIX': ('zip_prefixes', 'csv'),
        'VISITING_ZIP_PREFIX': ('zip_prefixes', 'csv'),
        'ZIP_ANY': ('zip_prefixes', 'csv'),
        'SNI_PREFIX': ('industry_ids', 'm2m_industry_by_sni'),
        'LEGALGROUP_CODE': ('legal_form_ids', 'm2m_legal_form'),
        'TURNOVER_INTERVAL': ('net_sales_magnitude_ids', 'm2m_magnitude_by_key'),
        'NBR_EMPLOYEES_INTERVAL': ('employee_magnitude_ids', 'm2m_magnitude_by_key'),
        'F_TAX': ('f_tax', 'select'),
        'MOMS': ('moms', 'select'),
        'ACCOUNTANT_RESERVATION': ('accountant_reservation', 'select'),
        'ACCOUNTANT_OBLIGATION': ('accountant_obligation', 'select'),
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
        'NET_PROFIT_LOSS': (('net_profit_loss_min', 'net_profit_loss_max'), 'range_float'),
        'GROWTH_PCT': (('growth_pct_min', 'growth_pct_max'), 'range_float'),
        'SOLIDITY_PCT': (('solidity_pct_min', 'solidity_pct_max'), 'range_float'),
        'EMPLOYEES_EXACT': (('employees_min', 'employees_max'), 'range_int'),
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
        vals['industry_ids'] = [(5, 0, 0)]
        vals['employee_magnitude_ids'] = [(5, 0, 0)]
        vals['net_sales_magnitude_ids'] = [(5, 0, 0)]
        return vals

    def _resolve_filters_to_vals(self, filters: list) -> dict:
        """Decode a list of API filter dicts ({filterCategory, SelectOption|
        SelectRange}) into a field-write vals dict, starting from a clean
        slate. Shared by preset apply, preset save and built-in seeding.
        Unknown / no-longer-supported categories are logged and skipped."""
        vals = self._reset_filters()
        for f in filters or []:
            cat = f.get('filterCategory')
            entry = self._filter_to_field_map.get(cat)
            if not entry:
                _logger.info("bizfinder preset ignores unsupported filter %s", cat)
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
                rng = f.get('SelectRange') or {}
                lo_field, hi_field = target
                if rng.get('min'):
                    vals[lo_field] = rng['min']
                if rng.get('max'):
                    vals[hi_field] = rng['max']
            elif kind == 'range_months_to_date':
                from dateutil.relativedelta import relativedelta
                today = fields.Date.context_today(self)
                rng = f.get('SelectRange') or {}
                lo_field, hi_field = target
                if rng.get('max') is not None:
                    vals[lo_field] = today - relativedelta(months=int(rng['max']))
                if rng.get('min') is not None:
                    vals[hi_field] = today - relativedelta(months=int(rng['min']))
        return vals
