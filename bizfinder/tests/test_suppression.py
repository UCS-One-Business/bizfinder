
"""Suppression of already-known companies in the prospect search.

``action_search`` always collects the org numbers of existing CRM leads and
company contacts and sends them to the API as an EXCLUDE_ORG_NUMBERS machine
filter, so known companies never consume result-page slots. An oversized
suppression set skips the server-side filter (falling back to result-page
deduplication) instead of blocking the search.
"""

from unittest.mock import patch

from odoo.addons.bizfinder.models import bizfinder_filter_mixin
from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestSuppression(BizfinderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.lead = cls.env['crm.lead'].create({
            'name': 'Existing Bizfinder lead',
            'company_organisation_number': '5511122233',
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Existing Customer AB',
            'is_company': True,
            'company_registry': '556677-8899',
        })

    def _search_payloads(self, wizard):
        """Run action_search and capture the filter payloads sent to
        preview() and search()."""
        captured = {}

        def _preview(_model, values):
            captured['preview'] = values
            return 0

        def _search(_model, values, skip=0, take=200):
            captured['search'] = values
            return []

        with self.mock_client(preview=_preview, search=_search):
            wizard.action_search()
        return captured

    @staticmethod
    def _exclude_entry(values):
        return next(
            (v for v in values if v.get('filterCategory') == 'EXCLUDE_ORG_NUMBERS'),
            None,
        )

    def test_search_sends_exclusions(self):
        wizard = self._new_wizard()
        captured = self._search_payloads(wizard)
        for key in ('preview', 'search'):
            entry = self._exclude_entry(captured[key])
            self.assertIsNotNone(entry, f"no EXCLUDE_ORG_NUMBERS in {key} payload")
            self.assertIn(5511122233, entry['SelectOption'])
            # Partner org number is normalized (hyphen stripped).
            self.assertIn(5566778899, entry['SelectOption'])

    def test_oversized_suppression_falls_back(self):
        """Beyond the payload limit the search still runs, just without the
        server-side filter; the result-page dedup is the safety net."""
        wizard = self._new_wizard()
        with patch.object(bizfinder_filter_mixin, 'SUPPRESSION_MAX', 1):
            captured = self._search_payloads(wizard)
        self.assertIsNone(self._exclude_entry(captured['preview']))
        self.assertIsNone(self._exclude_entry(captured['search']))
