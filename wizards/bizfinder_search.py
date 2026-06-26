# -*- coding: utf-8 -*-

import logging
from markupsafe import escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

_logger = logging.getLogger(__name__)


class BizfinderSearch(models.TransientModel):
    _name = 'bizfinder.search'
    _inherit = 'bizfinder.filter.mixin'
    _description = 'Bizfinder Search Wizard'

    @api.depends('preset_id')
    def _compute_display_name(self):
        # Override the framework-default "<model>,<id>" / "New" so the
        # breadcrumb reads as a real page name regardless of save state.
        for rec in self:
            rec.display_name = "Prospect"

    # ------------------------------------------------------------------- preset
    preset_id = fields.Many2one('bizfinder.preset', string='Preset')
    preset_description = fields.Text(
        related='preset_id.description', string='Preset description', readonly=True)

    # ------------------------------------------------- m2m filters (own tables)
    region_ids = fields.Many2many(
        'bizfinder.region',
        string='Regions',
        help="Pick one or more Swedish counties (län) to limit the search.",
    )
    industry_ids = fields.Many2many(
        'bizfinder.industry',
        'bizfinder_search_industry_rel', 'wizard_id', 'industry_id',
        string='Industries',
        help="Curated industry shortcuts. Each expands to its SNI prefixes.",
    )
    employee_magnitude_ids = fields.Many2many(
        'bizfinder.magnitude',
        'bizfinder_search_employee_magnitude_rel', 'wizard_id', 'magnitude_id',
        string='Employees',
        domain="[('kind', '=', 'employees')]",
        help="Find companies by how many people they employ. Pick one or "
             "more size bands (e.g. Small (10–49)). Leave empty to include "
             "companies of every size.",
    )
    net_sales_magnitude_ids = fields.Many2many(
        'bizfinder.magnitude',
        'bizfinder_search_net_sales_magnitude_rel', 'wizard_id', 'magnitude_id',
        string='Turnover',
        domain="[('kind', '=', 'net_sales')]",
        help="Find companies by their yearly revenue. Pick one or more "
             "ranges (e.g. 1–10 Mkr). Leave empty to include companies of "
             "every size.",
    )
    post_community_ids = fields.Many2many(
        'bizfinder.community',
        'bizfinder_search_post_community_rel', 'wizard_id', 'community_id',
        string='Municipalities (postal)',
        help="Postal-address kommun. Start typing to filter.",
    )
    alt_community_ids = fields.Many2many(
        'bizfinder.community',
        'bizfinder_search_alt_community_rel', 'wizard_id', 'community_id',
        string='Kommun',
        help="Matches registered OR visiting address kommun.",
    )
    legal_form_ids = fields.Many2many(
        'bizfinder.legal.form',
        'bizfinder_search_legal_form_rel', 'wizard_id', 'legal_form_id',
        string='Legal forms',
        default=lambda self: self._default_legal_form_ids(),
    )

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

    # ------------------------------------------------------------------- preset

    @api.onchange('preset_id')
    def _onchange_preset_id(self):
        """Apply the selected preset's filters. Clearing the preset leaves the
        current filters in place (use Clear if you want a clean slate)."""
        if not self.preset_id:
            return
        vals = self._resolve_filters_to_vals(self.preset_id._build_values())
        for fname, value in vals.items():
            self[fname] = value

    def action_save_preset(self):
        """Open the dialog that stores the current filters as a new preset."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Save filters as preset'),
            'res_model': 'bizfinder.preset.save',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_wizard_id': self.id},
        }

    def action_update_preset(self):
        """Overwrite the selected preset's filters with the current ones, so
        it becomes the new continuous version of that preset."""
        self.ensure_one()
        if not self.preset_id:
            raise UserError(_("Select a preset first, then update it."))
        self.preset_id.write(
            self.preset_id._resolve_filters_to_vals(self._build_values()))
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Preset updated'),
                'message': _("'%s' now matches the current filters.") % self.preset_id.name,
                'type': 'success',
                'sticky': False,
            },
        }

    def action_clear_preset(self):
        """Detach the selected preset (filters are kept)."""
        self.ensure_one()
        self.preset_id = False

    def action_manage_presets(self):
        """Open the preset list to add / edit / delete presets."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Presets'),
            'res_model': 'bizfinder.preset',
            'view_mode': 'list,form',
            'target': 'current',
        }

    # --------------------------------------------------------------- selection

    def action_select_all(self):
        """Native one-shot select of every result row."""
        self.ensure_one()
        self.result_line_ids.selected = True

    def action_deselect_all(self):
        self.ensure_one()
        self.result_line_ids.selected = False

    # --------------------------------------------------------------- entry/search

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

    # ---------------------------------------------------------------- leads

    @staticmethod
    def _format_notes(data: dict) -> str:
        """Render every field of a revealed prospect into HTML for the lead's
        Bizfinder tab. `data` is the JSON dict returned by the
        /api/insight/reveal endpoint."""
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

        # Catch-all: render any field the reveal returned that the curated
        # sections above don't already cover, so the lead carries the full
        # payload rather than only the keys we happened to enumerate.
        rendered_keys = {
            'name', 'organisationNumber', 'vatNumber', 'description',
            'legalEntityText', 'legalEntity', 'postCommunity',
            'companyFormedDate', 'registrationDate', 'statusDate',
            'numberOfUnits', 'directorName', 'directorRole', 'phone', 'fax',
            'address', 'postCode', 'city', 'visitingAddress',
            'visitingPostCode', 'visitingCity', 'visitingCommunity',
            'registeredAddress', 'registeredPostCode', 'registeredCity',
            'employees', 'turnOver', 'accountDateTo', 'accountMonths',
            'netSales', 'netOperatingIncome', 'operatingResult',
            'profitLossAfterFin', 'netProfitLoss', 'growthPct',
            'headcountChangePct', 'solidityPct', 'operatingMarginPct',
            'profitMarginPct', 'quickRatioPct', 'turnoverPerEmployee',
            'cashAtBank', 'totalAssets', 'totalEquity', 'currentLiabilities',
            'longTermDebts', 'dividend', 'accountantObligation',
        }

        def humanize(key: str) -> str:
            import re
            spaced = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', key)
            return spaced[:1].upper() + spaced[1:]

        other = "".join(
            kv(humanize(k), v)
            for k, v in data.items()
            if k not in rendered_keys and not isinstance(v, (dict, list))
        )
        if other:
            sections.append(f"<p><b>Other data</b></p><ul>{other}</ul>")

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

        # Tag the lead's Source so it reads as "Bizfinder" rather than the
        # blank/default a manual lead would get. Also drives the Bizfinder
        # tab visibility (crm.lead.is_bizfinder_lead).
        source = self.env.ref('bizfinder.utm_source_bizfinder', raise_if_not_found=False)

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
                'source_id': source.id if source else False,
                'bizfinder_data': self._format_notes(data) or False,
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


class BizfinderPresetSave(models.TransientModel):
    _name = 'bizfinder.preset.save'
    _description = 'Bizfinder Save Preset Dialog'

    wizard_id = fields.Many2one('bizfinder.search', required=True, ondelete='cascade')
    name = fields.Char(string='Preset name', required=True)
    description = fields.Text(string='Description')

    def action_save(self):
        self.ensure_one()
        preset = self.env['bizfinder.preset'].create({
            'name': self.name,
            'description': self.description or False,
        })
        # Snapshot the wizard's current filters onto the new preset's fields.
        preset.write(preset._resolve_filters_to_vals(self.wizard_id._build_values()))
        self.wizard_id.preset_id = preset
        return {
            'type': 'ir.actions.act_window',
            'name': 'Prospect Search',
            'res_model': 'bizfinder.search',
            'res_id': self.wizard_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
