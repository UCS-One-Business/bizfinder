
"""Suppression of already-known companies in the prospect search.

With the exclude toggles on (the wizard default), ``action_search`` collects
the org numbers of existing CRM leads and company contacts and sends them to
the API as an EXCLUDE_ORG_NUMBERS machine filter, so known companies never
consume result-page slots. The toggles are independent; an oversized
suppression set raises instead of silently truncating.
"""

from unittest.mock import patch

from odoo.addons.bizfinder.models import bizfinder_filter_mixin
from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.exceptions import UserError
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

    def test_toggles_on_send_exclusions(self):
        wizard = self._new_wizard()
        self.assertTrue(wizard.exclude_crm_leads)
        self.assertTrue(wizard.exclude_partners)
        captured = self._search_payloads(wizard)
        for key in ('preview', 'search'):
            entry = self._exclude_entry(captured[key])
            self.assertIsNotNone(entry, f"no EXCLUDE_ORG_NUMBERS in {key} payload")
            self.assertIn(5511122233, entry['SelectOption'])
            # Partner org number is normalized (hyphen stripped).
            self.assertIn(5566778899, entry['SelectOption'])

    def test_lead_toggle_only(self):
        wizard = self._new_wizard(exclude_partners=False)
        entry = self._exclude_entry(self._search_payloads(wizard)['search'])
        self.assertIn(5511122233, entry['SelectOption'])
        self.assertNotIn(5566778899, entry['SelectOption'])

    def test_toggles_off_send_no_exclusions(self):
        wizard = self._new_wizard(exclude_crm_leads=False, exclude_partners=False)
        captured = self._search_payloads(wizard)
        self.assertIsNone(self._exclude_entry(captured['preview']))
        self.assertIsNone(self._exclude_entry(captured['search']))

    def test_oversized_suppression_raises(self):
        wizard = self._new_wizard()
        with patch.object(bizfinder_filter_mixin, 'SUPPRESSION_MAX', 1), \
                self.mock_client(), self.assertRaises(UserError):
            wizard.action_search()

    def test_preset_carries_toggles(self):
        """Saving a preset snapshots the toggles; applying it restores them."""
        wizard = self._new_wizard(exclude_crm_leads=False, exclude_partners=False)
        save = self.env['bizfinder.preset.save'].create({
            'wizard_id': wizard.id,
            'name': 'No suppression',
        })
        save.action_save()
        preset = wizard.preset_id
        self.assertFalse(preset.exclude_crm_leads)
        self.assertFalse(preset.exclude_partners)

        other = self._new_wizard()
        other.preset_id = preset
        other._onchange_preset_id()
        self.assertFalse(other.exclude_crm_leads)
        self.assertFalse(other.exclude_partners)
