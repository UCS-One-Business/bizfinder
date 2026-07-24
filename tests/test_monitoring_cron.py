
"""Tests for the daily monitoring cron (bizfinder.company.event
.cron_sync_monitoring): event-row creation, chatter posts, severe-only
activities, idempotent re-runs and the events_last_pull config parameter."""

from odoo.addons.bizfinder.models.bizfinder_monitoring import EVENTS_LAST_PULL_PARAM
from odoo.addons.bizfinder.tests.common import BizfinderTestCommon
from odoo.tests import tagged


@tagged('post_install', '-at_install')
class TestBizfinderMonitoringCron(BizfinderTestCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesman = cls.env['res.users'].create({
            'name': 'Bizfinder Salesman',
            'login': 'bizfinder_cron_salesman',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Nordfält Bygg AB',
            'is_company': True,
            'company_registry': '556677-8899',
            'bizfinder_monitored': True,
            'user_id': cls.salesman.id,
        })
        cls.Event = cls.env['bizfinder.company.event']
        # The database may carry monitored partners / an events_last_pull
        # param from real use; neutralize both so cron assertions only see
        # this test's own partner (changes roll back with the transaction).
        cls.env['res.partner'].search([
            ('bizfinder_monitored', '=', True),
            ('id', '!=', cls.partner.id),
        ]).write({'bizfinder_monitored': False})
        cls.env['ir.config_parameter'].sudo().set_param(EVENTS_LAST_PULL_PARAM, False)

    def _run_cron(self, **mock_kwargs):
        with self.mock_client(**mock_kwargs):
            self.Event.cron_sync_monitoring()

    def _partner_events(self):
        return self.Event.search([('partner_id', '=', self.partner.id)])

    def _status_only_first(self):
        return [self.sample_company_status_rows()[0]]

    def test_cron_noop_without_monitored_partners(self):
        self.partner.bizfinder_monitored = False
        called = []

        def fake_events(_model, *args, **kwargs):
            called.append(True)
            return []

        self._run_cron(events=fake_events)
        self.assertFalse(called)
        self.assertFalse(self._partner_events())

    def test_cron_creates_events_and_syncs_status(self):
        self._run_cron(company_status=self._status_only_first())
        events = self._partner_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(
            sorted(events.mapped('event_type')), ['ADDRESS_CHANGED', 'F_TAX_LOST'])
        f_tax = events.filtered(lambda e: e.event_type == 'F_TAX_LOST')
        self.assertEqual(f_tax.org_number, '5566778899')
        self.assertEqual(f_tax.old_value, 'true')
        self.assertEqual(f_tax.new_value, 'false')
        self.assertEqual(str(f_tax.detected_at), '2025-08-02 09:30:00')
        # The status sync ran too.
        self.assertEqual(self.partner.bizfinder_status_code, 100)
        self.assertTrue(self.partner.bizfinder_last_sync)

    def test_cron_posts_chatter(self):
        before = self.partner.message_ids
        self._run_cron(company_status=self._status_only_first())
        new_messages = self.partner.message_ids - before
        bodies = ' '.join(new_messages.mapped(lambda m: str(m.body)))
        self.assertIn('F-tax lost', bodies)
        self.assertIn('Address changed', bodies)
        self.assertIn('Storgatan 1', bodies)
        self.assertIn('Nygatan 2', bodies)

    def test_activity_for_severe_types_only(self):
        self._run_cron(company_status=self._status_only_first())
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.partner.id),
        ])
        # Only F_TAX_LOST is severe; ADDRESS_CHANGED must not schedule one.
        self.assertEqual(len(activities), 1)
        self.assertIn('F-tax lost', activities.summary)
        self.assertEqual(activities.user_id, self.salesman)

    def test_no_activity_without_salesperson(self):
        self.partner.user_id = False
        self._run_cron(company_status=self._status_only_first())
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.partner.id),
        ])
        self.assertFalse(activities)
        # The event row and chatter still landed.
        self.assertEqual(len(self._partner_events()), 2)

    def test_status_changed_severe_only_when_inactive(self):
        status_event = [{
            'orgNumber': '5566778899',
            'companyName': 'Nordfält Bygg AB',
            'eventType': 'STATUS_CHANGED',
            'oldValue': 'Aktivt',
            'newValue': 'Konkurs inledd',
            'detectedAt': '2025-08-03T10:00:00Z',
        }]
        inactive = self._status_only_first()
        inactive[0].update(statusCode=310, statusText='Konkurs inledd')
        self._run_cron(company_status=inactive, events=status_event)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.partner.id),
        ])
        self.assertEqual(len(activities), 1)
        self.assertIn('Status changed', activities.summary)

    def test_status_changed_back_to_active_not_severe(self):
        status_event = [{
            'orgNumber': '5566778899',
            'companyName': 'Nordfält Bygg AB',
            'eventType': 'STATUS_CHANGED',
            'oldValue': 'Vilande',
            'newValue': 'Aktivt',
            'detectedAt': '2025-08-03T10:00:00Z',
        }]
        self._run_cron(company_status=self._status_only_first(), events=status_event)
        activities = self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'),
            ('res_id', '=', self.partner.id),
        ])
        self.assertFalse(activities)

    def test_idempotent_second_run(self):
        self._run_cron(company_status=self._status_only_first())
        events_after_first = self._partner_events()
        messages_after_first = len(self.partner.message_ids)
        # Same payload again: no duplicate events, no duplicate chatter.
        self._run_cron(company_status=self._status_only_first())
        self.assertEqual(self._partner_events(), events_after_first)
        self.assertEqual(len(self.partner.message_ids), messages_after_first)

    def test_config_param_advances(self):
        param = self.env['ir.config_parameter'].sudo()
        self.assertFalse(param.get_param(EVENTS_LAST_PULL_PARAM))
        self._run_cron(company_status=self._status_only_first())
        self.assertEqual(
            param.get_param(EVENTS_LAST_PULL_PARAM), '2025-08-02T09:30:00Z')

    def test_first_run_uses_lookback_since(self):
        seen = []

        def fake_events(_model, org_numbers, since=None, **kwargs):
            seen.append(since)
            return []

        self._run_cron(company_status=self._status_only_first(), events=fake_events)
        self.assertEqual(len(seen), 1)
        self.assertTrue(seen[0])  # 30-day lookback string, never None

    def test_second_run_uses_stored_since(self):
        self._run_cron(company_status=self._status_only_first())
        seen = []

        def fake_events(_model, org_numbers, since=None, **kwargs):
            seen.append(since)
            return []

        self._run_cron(company_status=self._status_only_first(), events=fake_events)
        self.assertEqual(seen, ['2025-08-02T09:30:00Z'])
