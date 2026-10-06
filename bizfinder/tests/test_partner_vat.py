"""VAT enrichment through Pick and Sync now, with a mocked registry service."""

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBizfinderPartnerVat(BizfinderTestCommon):

    def _enrich(self, action, org='559900-1236', moms=True, **partner_vals):
        partner = self.env['res.partner'].create({
            'name': 'Kund AB',
            'is_company': True,
            'company_registry': org,
            'country_id': self.env.ref('base.se').id,
            **partner_vals,
        })
        status = {'orgNumber': org, 'statusCode': 100}
        if moms != 'missing':
            status['moms'] = moms
        lookup = [{'name': 'Register AB', 'organisationNumber': org}]
        with self.mock_client(lookup=lookup, company_status=[status]):
            if action == 'pick':
                wizard = self.env['bizfinder.partner.lookup'].create({
                    'query': 'Kund', 'partner_id': partner.id,
                })
                wizard.action_search()
                wizard.line_ids.action_pick()
            else:
                partner.action_bizfinder_sync()
        return partner

    def test_malformed_org_does_not_generate_vat(self):
        for action in ('pick', 'sync'):
            for org in ('559900123', '55990012360', '55990012AB', '５５９９００１２３６'):
                with self.subTest(action=action, org=org):
                    partner = self._enrich(action, org=org)
                    self.assertFalse(partner.vat)
                    self.assertEqual(partner.bizfinder_moms, 'yes')

    def test_registered_company_gets_normalized_swedish_vat(self):
        for action in ('pick', 'sync'):
            for org in ('559900-1236', '5599001236', ' 559900-1236 '):
                with self.subTest(action=action, org=org):
                    partner = self._enrich(action, org=org)
                    self.assertEqual(partner.vat, 'SE559900123601')
                    self.assertEqual(partner.bizfinder_moms, 'yes')

    def test_existing_vat_is_never_overwritten(self):
        for action in ('pick', 'sync'):
            for moms in (True, False, None, 'missing'):
                with self.subTest(action=action, moms=moms):
                    partner = self._enrich(action, moms=moms, vat='SE556016068001')
                    self.assertEqual(partner.vat, 'SE556016068001')

    def test_unregistered_or_unknown_company_keeps_empty_vat(self):
        for action in ('pick', 'sync'):
            for moms, expected in ((False, 'no'), (None, 'unknown'), ('missing', 'unknown')):
                with self.subTest(action=action, moms=moms):
                    partner = self._enrich(action, moms=moms)
                    self.assertFalse(partner.vat)
                    self.assertEqual(partner.bizfinder_moms, expected)

    def test_swedish_vat_with_foreign_or_missing_country(self):
        # Run this same suite with base_vat installed to exercise its real
        # prefix validation, without bypassing validation or changing country.
        for action in ('pick', 'sync'):
            for code in ('de', 'no', 'us', False):
                with self.subTest(action=action, country=code):
                    country = self.env.ref(f'base.{code}') if code else self.env['res.country']
                    partner = self._enrich(action, country_id=country.id)
                    self.assertEqual(partner.vat, 'SE559900123601')
                    self.assertEqual(partner.country_id, country)

    def test_pick_keeps_existing_name_rule(self):
        for name, expected in (('Kund', 'Register AB'), ('Kund AB', 'Kund AB')):
            with self.subTest(name=name):
                partner = self._enrich('pick', name=name)
                self.assertEqual(partner.name, expected)
                self.assertEqual(partner.vat, 'SE559900123601')
