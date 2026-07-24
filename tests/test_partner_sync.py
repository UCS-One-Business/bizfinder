
"""Tests for the res.partner Bizfinder status sync: field writes from the
company-status payload, the health classification matrix, and org-number
normalization ('556677-8899' -> API called with '5566778899')."""

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBizfinderPartnerSync(BizfinderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Nordfält Bygg AB',
            'is_company': True,
            'company_registry': '556677-8899',
        })

    def _status_row(self, **overrides):
        row = self.sample_company_status_rows()[0]
        row.update(overrides)
        return row

    def test_sync_writes_fields(self):
        with self.mock_client(company_status=[self._status_row()]):
            self.partner.bizfinder_sync_status()
        p = self.partner
        self.assertEqual(p.bizfinder_status_code, 100)
        self.assertEqual(p.bizfinder_status_text, 'Aktivt')
        self.assertTrue(p.bizfinder_active)
        self.assertEqual(p.bizfinder_f_tax, 'yes')
        self.assertEqual(p.bizfinder_moms, 'yes')
        self.assertEqual(p.bizfinder_solidity_pct, 47.2)
        self.assertEqual(p.bizfinder_growth_pct, 18.4)
        self.assertEqual(p.bizfinder_profit_margin_pct, 5.9)
        self.assertEqual(p.bizfinder_quick_ratio_pct, 132.0)
        self.assertEqual(p.bizfinder_net_sales, 42150.0)
        self.assertEqual(str(p.bizfinder_account_date_to), '2025-12-31')
        self.assertEqual(p.bizfinder_employees, '10-19 anställda')
        self.assertEqual(p.bizfinder_health, 'good')
        self.assertTrue(p.bizfinder_last_sync)

    def test_normalizes_org_number_for_api(self):
        called_with = []

        def fake_status(_model, org_numbers, *args, **kwargs):
            called_with.append(list(org_numbers))
            return [self._status_row()]

        with self.mock_client(company_status=fake_status):
            self.partner.bizfinder_sync_status()
        self.assertEqual(called_with, [['5566778899']])

    # ------------------------------------------------------- health matrix
    def _health_after(self, **overrides):
        with self.mock_client(company_status=[self._status_row(**overrides)]):
            self.partner.bizfinder_sync_status()
        return self.partner.bizfinder_health

    def test_health_good(self):
        self.assertEqual(self._health_after(), 'good')

    def test_health_critical_inactive(self):
        self.assertEqual(
            self._health_after(statusCode=310, statusText='Konkurs inledd'),
            'critical')
        self.assertFalse(self.partner.bizfinder_active)

    def test_health_critical_f_tax_lost(self):
        self.assertEqual(self._health_after(fTax=False), 'critical')
        self.assertEqual(self.partner.bizfinder_f_tax, 'no')

    def test_health_critical_low_solidity(self):
        self.assertEqual(self._health_after(solidityPct=9.9), 'critical')

    def test_health_warning_solidity(self):
        self.assertEqual(self._health_after(solidityPct=15.0), 'warning')

    def test_health_warning_growth(self):
        self.assertEqual(self._health_after(growthPct=-12.0), 'warning')

    def test_health_warning_quick_ratio(self):
        self.assertEqual(self._health_after(quickRatioPct=60.0), 'warning')

    def test_health_good_when_financials_missing(self):
        # Null financials must not trip the numeric thresholds.
        self.assertEqual(
            self._health_after(solidityPct=None, growthPct=None, quickRatioPct=None),
            'good')

    def test_health_unknown_f_tax_not_critical(self):
        self.assertEqual(self._health_after(fTax=None), 'good')
        self.assertEqual(self.partner.bizfinder_f_tax, 'unknown')

    # ------------------------------------------------------------- helpers
    def test_sync_skips_non_company_and_missing_org(self):
        person = self.env['res.partner'].create({'name': 'A Person'})
        calls = []

        def fake_status(_model, org_numbers, *args, **kwargs):
            calls.append(list(org_numbers))
            return []

        with self.mock_client(company_status=fake_status):
            person.bizfinder_sync_status()
        self.assertFalse(calls)
