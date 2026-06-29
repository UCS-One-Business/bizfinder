# -*- coding: utf-8 -*-

"""Tests for the manager-only "This month" billing-usage stat shown in the
search results toolbar -- the contextual replacement for the old standalone
"Bizfinder Usage" menu.

Covers: the display string compute, the manager gate on the action_search hook
(loads for managers, skipped for plain salesmen), resilience to a usage-endpoint
failure (must not abort the search), and the toolbar "Details" action that opens
the full usage form as a dialog.
"""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon


@tagged('post_install', '-at_install')
class TestBizfinderMonthUsage(BizfinderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # group_sale_manager implies group_sale_salesman (and base.group_user),
        # so the manager can run the search; the salesman deliberately is NOT a
        # manager so the gate is exercised in both directions.
        # Odoo 19 renamed the res.users groups m2m to ``group_ids``.
        cls.manager = cls.env['res.users'].create({
            'name': 'Bizfinder Manager',
            'login': 'bizfinder_manager',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_manager').id])],
        })
        cls.salesman = cls.env['res.users'].create({
            'name': 'Bizfinder Salesman',
            'login': 'bizfinder_salesman',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
        })

    def _wizard_as(self, user):
        # Create AND operate as the same user so there is no cross-user access on
        # the transient record.
        return self.env['bizfinder.search'].with_user(user).create({})

    # --------------------------------------------------------- display string
    def test_display_blank_until_loaded(self):
        wizard = self._new_wizard()
        self.assertFalse(wizard.month_usage_loaded)
        self.assertEqual(wizard.month_usage_display, '')

    def test_display_formats_loaded_usage(self):
        wizard = self._new_wizard()
        wizard.write({
            'month_usage_loaded': True,
            'month_reveals': 12,
            'month_amount': 114.0,
            'billing_currency': 'SEK',
        })
        self.assertEqual(wizard.month_usage_display, '12 reveals · 114.00 SEK')

    # ------------------------------------------------------- action_search hook
    def test_search_loads_usage_for_manager(self):
        wizard = self._wizard_as(self.manager)
        with self.mock_client():
            wizard.action_search()
        self.assertTrue(wizard.month_usage_loaded)
        self.assertEqual(wizard.month_reveals, self.USAGE['reveals'])
        self.assertEqual(wizard.month_amount, self.USAGE['amount'])

    def test_search_skips_usage_for_non_manager(self):
        wizard = self._wizard_as(self.salesman)
        with self.mock_client():
            wizard.action_search()
        # Search still ran and produced results...
        self.assertTrue(wizard.result_line_ids)
        # ...but the manager-only usage stat was never fetched.
        self.assertFalse(wizard.month_usage_loaded)
        self.assertEqual(wizard.month_reveals, 0)

    def test_search_survives_usage_failure(self):
        # A usage hiccup must never abort the search the user actually asked for.
        def boom(_model, *args, **kwargs):
            raise ValueError("usage endpoint down")

        wizard = self._wizard_as(self.manager)
        with self.mock_client(usage=boom):
            wizard.action_search()
        self.assertTrue(wizard.result_line_ids)
        self.assertFalse(wizard.month_usage_loaded)

    # ---------------------------------------------------------- Details dialog
    def test_open_month_usage_returns_dialog_for_manager(self):
        wizard = self._wizard_as(self.manager)
        with self.mock_client():
            action = wizard.action_open_month_usage()
        self.assertEqual(action['res_model'], 'bizfinder.usage')
        self.assertEqual(action['target'], 'new')

    def test_open_month_usage_blocked_for_non_manager(self):
        wizard = self._wizard_as(self.salesman)
        with self.mock_client():
            with self.assertRaises(AccessError):
                wizard.action_open_month_usage()
