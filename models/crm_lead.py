# -*- coding: utf-8 -*-

from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    company_vat_number = fields.Char(string='VAT number')
    company_organisation_number = fields.Char(string='Organisation number')
    company_employees = fields.Char(string='Employees (bucket)')
    company_turnover = fields.Char(string='Turnover (bucket)')
    company_legal_entity = fields.Char(string='Legal form')
    company_director_name = fields.Char(string='Top director')
    company_director_role = fields.Char(string='Director role')
    company_visiting_address = fields.Char(string='Visiting address')
    company_visiting_post_code = fields.Char(string='Visiting ZIP')
    company_visiting_city = fields.Char(string='Visiting city')
    company_visiting_community = fields.Char(string='Visiting municipality')
    company_post_community = fields.Char(string='Municipality')
    company_registered_address = fields.Char(string='Registered address')
    company_registered_city = fields.Char(string='Registered city')
    company_number_of_units = fields.Integer(string='Units')
    company_net_sales = fields.Float(string='Net sales')
    company_operating_result = fields.Float(string='Operating result')
    company_net_profit_loss = fields.Float(string='Net profit/loss')
    company_account_date_to = fields.Date(string='Statement date')
    company_solidity_pct = fields.Float(string='Solidity %')
    company_growth_pct = fields.Float(string='Growth %')

    _company_organisation_number_uniq = models.Constraint(
        'unique(company_organisation_number)',
        'A CRM lead already exists for this organisation number.',
    )
