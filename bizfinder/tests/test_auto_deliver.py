
"""Preset auto-delivery: the nightly cron runs subscribed presets and creates
CRM leads from redacted prospect rows - never calling reveal(), so nothing is
billed."""

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestAutoDeliver(BizfinderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesperson = cls.env['res.users'].create({
            'name': 'Delivery Rep',
            'login': 'delivery.rep@example.com',
            'group_ids': [(4, cls.env.ref('sales_team.group_sale_salesman').id)],
        })
        # Real databases may already carry subscribed presets (demo data);
        # switch them off so the cron only runs this test's preset.
        cls.env['bizfinder.preset'].search([
            ('auto_deliver', '=', True),
        ]).write({'auto_deliver': False})
        cls.preset = cls.env['bizfinder.preset'].create({
            'name': 'Nightly builders',
            'auto_deliver': True,
            'auto_deliver_user_id': cls.salesperson.id,
            'auto_deliver_max': 2,
            'auto_deliver_new_only': True,
        })

    def _run_cron(self, **mock_kwargs):
        captured = {}

        def _search(_model, values, skip=0, take=200):
            captured['values'] = values
            captured['take'] = take
            return self.sample_search_rows()[:take]

        def _reveal(_model, org_numbers):
            captured['revealed'] = org_numbers
            return []

        with self.mock_client(search=_search, reveal=_reveal, **mock_kwargs):
            self.env['bizfinder.preset'].cron_auto_deliver()
        return captured

    def test_delivers_capped_assigned_leads_without_reveal(self):
        captured = self._run_cron()
        self.assertEqual(captured['take'], 2)
        self.assertNotIn('revealed', captured, "auto-delivery must never reveal")

        leads = self.env['crm.lead'].search([
            ('source_id', '=', self.env.ref('bizfinder.utm_source_bizfinder').id),
            ('user_id', '=', self.salesperson.id),
        ])
        self.assertEqual(len(leads), 2)
        for lead in leads:
            self.assertEqual(lead.user_id, self.salesperson)
            self.assertFalse(lead.phone)
            self.assertFalse(lead.street)
            self.assertTrue(lead.company_organisation_number)
            self.assertIn('Nightly builders', lead.bizfinder_data)
        self.assertTrue(self.preset.auto_deliver_last_run)

    def test_second_run_sends_first_seen_since_and_skips_existing(self):
        self._run_cron()
        last_run = self.preset.auto_deliver_last_run
        before = self.env['crm.lead'].search_count([
            ('user_id', '=', self.salesperson.id),
        ])

        captured = self._run_cron()
        entry = next(
            (v for v in captured['values']
             if v.get('filterCategory') == 'FIRST_SEEN_SINCE'),
            None,
        )
        self.assertIsNotNone(entry)
        self.assertEqual(
            entry['SelectRange']['min'],
            last_run.strftime('%Y-%m-%dT%H:%M:%SZ'),
        )
        # Same rows returned again -> org constraint respected, no new leads.
        self.assertEqual(
            self.env['crm.lead'].search_count([
                ('user_id', '=', self.salesperson.id),
            ]),
            before,
        )
