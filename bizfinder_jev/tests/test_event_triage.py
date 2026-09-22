from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.ucs_core.services.jev_service import JevService
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


def _answers(kind='opportunity', confidence=0.8, urgency=0.7):
    return {
        'kind': {
            'type': 'choice', 'choice': kind, 'confidence': confidence,
            'probabilities': {'opportunity': 0.7, 'follow_up': 0.25, 'informational': 0.05},
        },
        'urgent': {'type': 'noul', 'noul': urgency},
    }


@tagged('post_install', '-at_install')
class TestBizfinderJevTriage(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.write({'jev_api_key': 'jev-test-key', 'bizfinder_jev_triage_enabled': True})
        cls.salesman = cls.env['res.users'].create({
            'name': 'Triage Salesman',
            'login': 'bizfinder_jev_salesman',
            'group_ids': [(6, 0, [cls.env.ref('sales_team.group_sale_salesman').id])],
        })
        cls.partner = cls.env['res.partner'].create({
            'name': 'Nordfält Bygg AB',
            'is_company': True,
            'company_registry': '556677-8899',
            'bizfinder_monitored': True,
            'customer_rank': 1,
            'user_id': cls.salesman.id,
            'bizfinder_net_sales': 12000.0,
            'bizfinder_employees': '20-49',
        })
        cls.env['crm.lead'].create({
            'name': 'Ramavtal 2027', 'type': 'opportunity',
            'partner_id': cls.partner.id, 'expected_revenue': 250000,
        })
        cls.Event = cls.env['bizfinder.company.event']

    def _event(self, event_type='DIRECTOR_CHANGED', **vals):
        return self.Event.create({
            'partner_id': self.partner.id,
            'org_number': '5566778899',
            'company_name': self.partner.name,
            'event_type': event_type,
            'old_value': vals.pop('old_value', 'Anna Lind'),
            'new_value': vals.pop('new_value', 'Erik Berg'),
            'detected_at': vals.pop('detected_at', datetime(2026, 9, 1, 8, 0)),
            **vals,
        })

    def _activities(self):
        return self.env['mail.activity'].search([
            ('res_model', '=', 'res.partner'), ('res_id', '=', self.partner.id),
        ])

    def test_notify_triages_non_severe_event_and_books_activity(self):
        event = self._event()
        with patch.object(JevService, 'system_one', return_value=_answers()) as call:
            event._notify_partner(self.partner)

        self.assertEqual(event.jev_kind, 'opportunity')
        self.assertAlmostEqual(event.jev_confidence, 0.8)
        self.assertAlmostEqual(event.jev_urgency, 0.7)
        self.assertEqual(event.jev_probabilities['follow_up'], 0.25)
        company, state, questions = call.call_args.args
        self.assertEqual(company, self.company)
        self.assertEqual(state['event']['type'], 'Director changed')
        self.assertEqual(state['company']['relationship'], 'customer')
        self.assertEqual(state['company']['salesperson'], 'Triage Salesman')
        self.assertEqual(state['open_opportunities'][0]['name'], 'Ramavtal 2027')
        self.assertEqual(set(questions), {'kind', 'urgent'})
        self.assertEqual(
            set(questions['kind']['criteria']), {'opportunity', 'follow_up', 'informational'})
        activity = self._activities()
        self.assertEqual(len(activity), 1)
        self.assertEqual(activity.user_id, self.salesman)
        self.assertIn('Sales opportunity', activity.summary)
        self.assertEqual(
            activity.date_deadline, fields.Date.context_today(event) + timedelta(days=3))

    def test_low_urgency_gets_the_long_deadline(self):
        event = self._event()
        with patch.object(JevService, 'system_one', return_value=_answers('follow_up', urgency=0.2)):
            event._notify_partner(self.partner)
        self.assertEqual(event.jev_kind, 'follow_up')
        self.assertEqual(
            self._activities().date_deadline,
            fields.Date.context_today(event) + timedelta(days=14))

    def test_informational_books_no_activity(self):
        event = self._event('PHONE_CHANGED')
        with patch.object(JevService, 'system_one', return_value=_answers('informational', urgency=0.1)):
            event._notify_partner(self.partner)
        self.assertEqual(event.jev_kind, 'informational')
        self.assertFalse(self._activities())

    def test_severe_event_keeps_deterministic_alert_and_skips_jev(self):
        event = self._event('F_TAX_LOST', old_value='Yes', new_value='No')
        with patch.object(JevService, 'system_one') as call:
            event._notify_partner(self.partner)
        call.assert_not_called()
        self.assertFalse(event.jev_kind)
        self.assertEqual(len(self._activities()), 1)
        with self.assertRaises(UserError):
            event.action_jev_triage()

    def test_flag_off_is_inert(self):
        self.company.bizfinder_jev_triage_enabled = False
        event = self._event()
        with patch.object(JevService, 'system_one') as call:
            event._notify_partner(self.partner)
        call.assert_not_called()
        self.assertFalse(event.jev_kind)
        with self.assertRaises(UserError):
            event.action_jev_triage()

    def test_recent_events_exclude_self(self):
        older = self._event('ADDRESS_CHANGED', old_value='Storgatan 1', new_value='Nygatan 2',
                            detected_at=datetime(2026, 8, 1, 8, 0))
        event = self._event()
        with patch.object(JevService, 'system_one', return_value=_answers()) as call:
            event.action_jev_triage()
        state = call.call_args.args[1]
        self.assertEqual([e['type'] for e in state['recent_events']], ['Address changed'])
        self.assertFalse(older.jev_kind)

    def test_jev_failure_is_loud(self):
        event = self._event()
        with patch.object(JevService, 'system_one', side_effect=UserError('down')), \
                self.assertRaises(UserError):
            event.action_jev_triage()
        self.assertFalse(event.jev_kind)
