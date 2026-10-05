

from odoo import fields, models


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
