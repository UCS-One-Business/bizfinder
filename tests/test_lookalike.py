
"""Lookalike search: a Bizfinder search wizard pre-filled from the company
profile (employee/turnover buckets, legal form) of selected CRM leads."""

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestLookalike(BizfinderTestCommon):

    def _make_lead(self, **vals):
        return self.env['crm.lead'].create({
            'name': vals.pop('name', 'Bizfinder lead'),
            **vals,
        })

    def test_lookalike_prefills_wizard(self):
        leads = self._make_lead(
            name='Won builder',
            company_organisation_number='5500000001',
            company_employees='10-19 anställda',
            company_turnover='5000 - 9999 tkr',
            company_legal_entity='Aktiebolag',
        ) | self._make_lead(
            name='Won consultancy',
            company_organisation_number='5500000002',
            company_employees='50-99 anställda',
        )
        action = self.env['bizfinder.search'].action_lookalike_from_leads(leads)
        wizard = self.env['bizfinder.search'].browse(action['res_id'])

        emp_names = set(wizard.employee_magnitude_ids.mapped('name'))
        self.assertIn('Small (10–49)', emp_names)      # 10-19 anställda
        self.assertIn('Medium (50–199)', emp_names)    # 50-99 anställda
        # 5000 - 9999 tkr sits in the 1–10 Mkr band.
        self.assertIn('1–10 Mkr', set(wizard.net_sales_magnitude_ids.mapped('name')))
        self.assertIn('AB', set(wizard.legal_form_ids.mapped('code')))
        self.assertTrue(wizard.exclude_crm_leads)
        self.assertTrue(wizard.exclude_partners)

    def test_lookalike_without_data_raises(self):
        leads = self._make_lead(name='Manual lead, no company data')
        with self.assertRaises(UserError):
            self.env['bizfinder.search'].action_lookalike_from_leads(leads)
