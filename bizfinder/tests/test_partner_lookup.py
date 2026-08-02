
"""Tests for the bizfinder.partner.lookup wizard: search fills lines, the
query-length guard, and picking a line enriches an existing partner without
clobbering its name - or creates a new company partner when none is bound."""

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.exceptions import UserError
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBizfinderPartnerLookup(BizfinderTestCommon):

    def _new_lookup(self, **vals):
        return self.env['bizfinder.partner.lookup'].create(dict({'query': 'Nordfält'}, **vals))

    def test_search_fills_lines(self):
        wizard = self._new_lookup()
        with self.mock_client():
            wizard.action_search()
        self.assertEqual(len(wizard.line_ids), 2)
        first = wizard.line_ids.filtered(
            lambda l: l.organisation_number == '5566778899')
        self.assertEqual(first.name, 'Nordfält Bygg AB')
        self.assertEqual(first.city, 'Stockholm')
        self.assertEqual(first.legal_entity_text, 'Aktiebolag')

    def test_search_rejects_short_query(self):
        wizard = self._new_lookup(query='N')
        with self.mock_client(), self.assertRaises(UserError):
            wizard.action_search()

    def test_search_replaces_previous_lines(self):
        wizard = self._new_lookup()
        with self.mock_client():
            wizard.action_search()
            wizard.action_search()
        self.assertEqual(len(wizard.line_ids), 2)

    def test_pick_enriches_existing_partner_without_clobbering_name(self):
        partner = self.env['res.partner'].create({
            'name': 'My Existing Customer Name',
            'is_company': False,
        })
        wizard = self._new_lookup(partner_id=partner.id)
        with self.mock_client():
            wizard.action_search()
            line = wizard.line_ids.filtered(
                lambda l: l.organisation_number == '5566778899')
            action = line.action_pick()
        self.assertEqual(partner.name, 'My Existing Customer Name')
        self.assertEqual(partner.company_registry, '5566778899')
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.city, 'Stockholm')
        # The follow-up sync ran and filled status/financials.
        self.assertEqual(partner.bizfinder_health, 'good')
        self.assertTrue(partner.bizfinder_last_sync)
        self.assertEqual(action['res_model'], 'res.partner')
        self.assertEqual(action['res_id'], partner.id)

    def test_pick_does_not_overwrite_existing_city(self):
        partner = self.env['res.partner'].create({
            'name': 'Kund AB',
            'is_company': True,
            'city': 'Malmö',
        })
        wizard = self._new_lookup(partner_id=partner.id)
        with self.mock_client():
            wizard.action_search()
            wizard.line_ids.filtered(
                lambda l: l.organisation_number == '5566778899').action_pick()
        self.assertEqual(partner.city, 'Malmö')
        self.assertEqual(partner.company_registry, '5566778899')

    def test_pick_creates_new_partner_when_no_active_partner(self):
        wizard = self._new_lookup()
        with self.mock_client():
            wizard.action_search()
            line = wizard.line_ids.filtered(
                lambda l: l.organisation_number == '5566778899')
            action = line.action_pick()
        partner = self.env['res.partner'].browse(action['res_id'])
        self.assertEqual(partner.name, 'Nordfält Bygg AB')
        self.assertTrue(partner.is_company)
        self.assertEqual(partner.company_registry, '5566778899')
        self.assertEqual(partner.city, 'Stockholm')
        # Redacted tier: lookup carries no street/phone and the sync must not
        # invent them.
        self.assertFalse(partner.street)
        self.assertFalse(partner.phone)
        self.assertEqual(partner.bizfinder_health, 'good')
