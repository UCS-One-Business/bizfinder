# -*- coding: utf-8 -*-

"""Behavioural tests for ``bizfinder.search.action_create_leads``.

Covers the full create-leads pipeline of the Bizfinder search wizard:

* the empty-selection and all-existing guards (raise before any client call);
* the billing-confirmation gate that defers creation until the user confirms;
* the reveal -> crm.lead field mapping and UTM source tagging;
* skipping orgs the reveal endpoint dropped, and the "nothing revealed" guard;
* the focused CRM act_window scoped to exactly the created lead ids.

Every external ``bizfinder.client`` call is mocked through
:class:`~odoo.addons.bizfinder.tests.common.BizfinderTestCommon` so the tests
never touch the network.
"""

from datetime import date

from odoo.tests import tagged
from odoo.exceptions import UserError

from .common import BizfinderTestCommon


@tagged('post_install', '-at_install')
class TestCreateLeads(BizfinderTestCommon):

    def _leads_for_orgs(self, orgs=None):
        """crm.lead records whose org number is in ``orgs`` (defaults to the
        shared fixture org numbers)."""
        orgs = orgs if orgs is not None else self.ORG_NUMBERS
        return self.env['crm.lead'].search([
            ('company_organisation_number', 'in', orgs),
        ])

    # ------------------------------------------------------------ guards

    def test_create_leads_requires_selection(self):
        """No line selected -> the empty-selection guard fires before the
        client is ever consulted, and no lead is created."""
        wizard = self._run_search()
        # Sanity: action_search did populate the result lines, none selected.
        self.assertEqual(len(wizard.result_line_ids), 3)
        self.assertFalse(self._selected_lines(wizard))

        with self.assertRaises(UserError) as cm:
            self._create_leads(wizard)
        self.assertEqual(str(cm.exception), 'Select at least one prospect first.')

        self.assertFalse(self._leads_for_orgs())

    def test_create_leads_all_existing_raises(self):
        """Every selected prospect already lives in CRM -> the dedup filter
        empties the selection and the all-existing guard raises. Leads are
        pre-seeded AFTER the search so action_search does not dedup them away."""
        wizard = self._run_search()
        wizard.action_select_all()
        self.assertEqual(len(self._selected_lines(wizard)), 3)

        # Pre-existing, non-Bizfinder leads (no source) for each org number.
        for org in self.ORG_NUMBERS:
            self.env['crm.lead'].create({
                'name': 'Pre-existing %s' % org,
                'company_organisation_number': org,
            })

        with self.assertRaises(UserError) as cm:
            self._create_leads(wizard)
        self.assertEqual(
            str(cm.exception), 'All selected prospects already exist in CRM.')

        # Still only the three pre-seeded leads, none tagged as Bizfinder.
        leads = self._leads_for_orgs()
        self.assertEqual(len(leads), 3)
        self.assertFalse(
            leads.filtered(lambda l: l.source_id == self.utm_source_bizfinder))

    # ------------------------------------------------------ billing gate

    def test_billing_gate_defers_then_confirm_creates_leads(self):
        """Without the confirmed context, action_create_leads returns the
        billing-gate dialog and creates nothing; confirming it then creates
        the leads."""
        wizard = self._run_search()
        wizard.action_select_all()

        action = self._create_leads(wizard, billing_confirmed=False)

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'bizfinder.reveal.confirm')
        self.assertEqual(action['target'], 'new')
        self.assertIn('res_id', action)

        # Gate only: no leads written yet.
        self.assertFalse(self._leads_for_orgs())

        confirm = self.env['bizfinder.reveal.confirm'].browse(action['res_id'])
        self.assertEqual(confirm.reveal_count, 3)
        self.assertAlmostEqual(confirm.price_per_reveal, 9.5)
        self.assertEqual(confirm.currency, 'SEK')
        self.assertAlmostEqual(confirm.estimated_total, 28.5)

        # Confirming re-enters action_create_leads with the confirmed context.
        with self.mock_client():
            result = confirm.action_confirm()

        leads = self._leads_for_orgs()
        self.assertEqual(len(leads), 3)
        for lead in leads:
            self.assertEqual(lead.source_id, self.utm_source_bizfinder)

        self.assertEqual(result['type'], 'ir.actions.act_window')
        self.assertEqual(result['res_model'], 'crm.lead')
        self.assertEqual(result['name'], 'Created Bizfinder Leads')

    # ----------------------------------------------------- field mapping

    def test_create_leads_maps_reveal_fields_and_source(self):
        """Confirmed happy path: the revealed payload maps onto the lead's
        native + custom fields, and the lead is tagged with the Bizfinder
        UTM source."""
        wizard = self._run_search()
        wizard.action_select_all()
        self._create_leads(wizard)

        lead = self.env['crm.lead'].search([
            ('company_organisation_number', '=', '5566778899'),
        ])
        self.assertEqual(len(lead), 1)

        # Name / partner.
        self.assertEqual(lead.name, 'Nordfält Bygg AB')
        self.assertEqual(lead.partner_name, 'Nordfält Bygg AB')

        # Native contact mapping.
        self.assertEqual(lead.phone, '+46 8 123 45 67')
        self.assertEqual(lead.street, 'Storgatan 1')
        self.assertEqual(lead.zip, '11122')
        self.assertEqual(lead.city, 'Stockholm')

        # Source / computed flag.
        self.assertEqual(lead.source_id, self.utm_source_bizfinder)
        self.assertTrue(lead.is_bizfinder_lead)

        # Custom org / classification fields.
        self.assertEqual(lead.company_organisation_number, '5566778899')
        self.assertEqual(lead.company_vat_number, 'SE556677889901')
        self.assertEqual(lead.company_employees, '10-19 anställda')
        self.assertEqual(lead.company_turnover, '10 000-49 999 tkr')
        self.assertEqual(lead.company_legal_entity, 'Aktiebolag')
        self.assertEqual(lead.company_director_name, 'Anna Nordfält')
        self.assertEqual(lead.company_director_role, 'VD')

        # Numeric / date fields.
        self.assertAlmostEqual(lead.company_net_sales, 42150.0)
        self.assertAlmostEqual(lead.company_operating_result, 3120.0)
        self.assertAlmostEqual(lead.company_net_profit_loss, 2480.0)
        self.assertAlmostEqual(lead.company_growth_pct, 18.4)
        self.assertAlmostEqual(lead.company_solidity_pct, 47.2)
        self.assertEqual(lead.company_number_of_units, 2)
        self.assertEqual(lead.company_account_date_to, date(2025, 12, 31))

        # Rendered Bizfinder tab carries the import banner.
        self.assertTrue(lead.bizfinder_data)
        self.assertIn(
            'Imported from Creditsafe via Bizfinder.', lead.bizfinder_data)

    # ------------------------------------------------- skip / nothing

    def test_create_leads_skips_org_without_reveal_data(self):
        """An org with no reveal payload is skipped, not created blank; the
        other two are created and the action targets exactly those two."""
        wizard = self._run_search()
        wizard.action_select_all()

        # Reveal drops org 5599887766 (the third sample row).
        action = self._create_leads(
            wizard, reveal=self.sample_reveal_rows()[:2])

        leads = self._leads_for_orgs()
        self.assertEqual(len(leads), 2)
        self.assertEqual(
            set(leads.mapped('company_organisation_number')),
            {'5566778899', '5560123456'},
        )
        self.assertFalse(self._leads_for_orgs(['5599887766']))

        domain = action['domain']
        self.assertEqual(domain[0][0], 'id')
        self.assertEqual(domain[0][1], 'in')
        self.assertEqual(len(domain[0][2]), 2)
        self.assertEqual(set(domain[0][2]), set(leads.ids))

    def test_create_leads_raises_when_nothing_revealed(self):
        """Reveal returns nothing -> every selected line is skipped and the
        final guard raises, with no lead created."""
        wizard = self._run_search()
        wizard.action_select_all()

        with self.assertRaises(UserError) as cm:
            self._create_leads(wizard, reveal=[])
        self.assertEqual(
            str(cm.exception),
            'No leads were created. The selected prospects could not be revealed.',
        )

        self.assertFalse(self._leads_for_orgs())

    # ------------------------------------------------- success action

    def test_create_leads_returns_action_scoped_to_created_ids(self):
        """The success act_window is the all-leads action narrowed to exactly
        the freshly created lead ids, with creation disabled."""
        wizard = self._run_search()
        wizard.action_select_all()
        action = self._create_leads(wizard)

        self.assertEqual(action['type'], 'ir.actions.act_window')
        self.assertEqual(action['res_model'], 'crm.lead')
        self.assertEqual(action['name'], 'Created Bizfinder Leads')

        leads = self._leads_for_orgs()
        self.assertEqual(len(leads), 3)

        domain = action['domain']
        self.assertEqual(domain[0][0], 'id')
        self.assertEqual(domain[0][1], 'in')
        self.assertEqual(set(domain[0][2]), set(leads.ids))

        self.assertEqual(action['context']['create'], False)
