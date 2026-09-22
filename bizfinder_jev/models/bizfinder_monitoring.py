from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

# The closed answer space. Rubrics are part of the classification, not
# decoration: Jev picks among these descriptions, the labels are for us.
KIND_CRITERIA = {
    'opportunity': (
        'Signals new or expanded business we could sell into: growth, '
        'expansion, new decision makers, stronger finances, new registrations.'
    ),
    'follow_up': (
        'A relationship change worth a call from the account manager but no '
        'direct sale: moves, renamed company, weakening finances, changed '
        'directors at a quiet account.'
    ),
    'informational': (
        'Record it, nothing to do: routine registry updates such as a new '
        'phone number or a corrected address, with no bearing on the '
        'business relationship.'
    ),
}
KIND_SELECTION = [
    ('opportunity', 'Sales opportunity'),
    ('follow_up', 'Account follow-up'),
    ('informational', 'Informational'),
]
ACTIONABLE_KINDS = ('opportunity', 'follow_up')
URGENT_THRESHOLD = 0.5
DEADLINE_DAYS_URGENT = 3
DEADLINE_DAYS_DEFAULT = 14
RECENT_EVENTS = 5


class BizfinderCompanyEvent(models.Model):
    _inherit = 'bizfinder.company.event'

    jev_kind = fields.Selection(KIND_SELECTION, string='AI Triage', readonly=True)
    jev_confidence = fields.Float(string='AI Confidence', readonly=True, digits=(3, 2))
    jev_urgency = fields.Float(
        string='AI Urgency', readonly=True, digits=(3, 2),
        help='Likelihood that the account manager should act within a week.',
    )
    jev_probabilities = fields.Json(readonly=True)

    # ------------------------------------------------------------ triage
    def _notify_partner(self, partner):
        result = super()._notify_partner(partner)
        company = partner.company_id or self.env.company
        if company.bizfinder_jev_triage_enabled and not self._is_severe(partner):
            self._jev_triage(partner)
        return result

    def action_jev_triage(self):
        """Form button: triage (or re-triage) one event on demand. Severe
        events have their deterministic alert and are not sent to Jev."""
        for event in self:
            if not event.partner_id:
                raise UserError(self.env._('This event is not linked to a company contact.'))
            company = event.partner_id.company_id or self.env.company
            if not company.bizfinder_jev_triage_enabled:
                raise UserError(self.env._('AI event triage is switched off for %s.', company.name))
            if event._is_severe(event.partner_id):
                raise UserError(self.env._('Severe events always alert the salesperson and are not triaged.'))
            event._jev_triage(event.partner_id)

    def _jev_triage(self, partner):
        self.ensure_one()
        company = partner.company_id or self.env.company
        answers = self.env['ucs.jev.service'].system_one(
            company, self._jev_state(partner), self._jev_questions())
        kind = answers['kind']
        urgency = answers['urgent']['noul']
        self.sudo().write({
            'jev_kind': kind['choice'],
            'jev_confidence': kind['confidence'],
            'jev_urgency': urgency,
            'jev_probabilities': kind['probabilities'],
        })
        if kind['choice'] in ACTIONABLE_KINDS and partner.user_id:
            days = DEADLINE_DAYS_URGENT if urgency >= URGENT_THRESHOLD else DEADLINE_DAYS_DEFAULT
            label = self._event_type_label(self.event_type)
            kind_label = dict(KIND_SELECTION)[kind['choice']]
            partner.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=self.env._("Bizfinder %(kind)s: %(label)s", kind=kind_label, label=label),
                note=self.env._(
                    "%(label)s: %(old)s → %(new)s. AI triage: %(kind)s "
                    "(confidence %(conf).0f%%, urgency %(urg).0f%%).",
                    label=label,
                    old=self.old_value or self.env._('(none)'),
                    new=self.new_value or self.env._('(none)'),
                    kind=kind_label,
                    conf=kind['confidence'] * 100,
                    urg=urgency * 100,
                ),
                user_id=partner.user_id.id,
                date_deadline=fields.Date.context_today(self) + timedelta(days=days),
            )

    @api.model
    def _jev_questions(self):
        return {
            'kind': {
                'type': 'choice',
                'instructions': (
                    'For the sales team responsible for this company, what '
                    'kind of event is this?'
                ),
                'criteria': dict(KIND_CRITERIA),
            },
            'urgent': {
                'type': 'noul',
                'instructions': (
                    'Should the account manager act on this event within a week?'
                ),
            },
        }

    def _jev_state(self, partner):
        """Everything Odoo knows that bears on the decision. The event row
        itself is thin (type, old, new); the signal comes from who the
        company is to us."""
        self.ensure_one()
        if partner.customer_rank and partner.supplier_rank:
            relationship = 'customer and supplier'
        elif partner.customer_rank:
            relationship = 'customer'
        elif partner.supplier_rank:
            relationship = 'supplier'
        else:
            relationship = 'prospect'
        opportunities = self.env['crm.lead'].search([
            ('partner_id', '=', partner.id), ('type', '=', 'opportunity'),
        ])
        recent = self.search([
            ('partner_id', '=', partner.id), ('id', '!=', self.id),
        ], limit=RECENT_EVENTS)
        return {
            'event': {
                'type': self._event_type_label(self.event_type),
                'old_value': self.old_value or None,
                'new_value': self.new_value or None,
                'detected_at': fields.Date.to_string(self.detected_at),
            },
            'company': {
                'name': partner.name,
                'relationship': relationship,
                'relationship_since': fields.Date.to_string(partner.create_date),
                'salesperson': partner.user_id.name or None,
                'registry_status': partner.bizfinder_status_text or None,
                'financial_health': partner.bizfinder_health or None,
                'net_sales_tkr': partner.bizfinder_net_sales or None,
                'growth_pct': partner.bizfinder_growth_pct or None,
                'employees': partner.bizfinder_employees or None,
            },
            'open_opportunities': [
                {
                    'name': lead.name,
                    'stage': lead.stage_id.name,
                    'expected_revenue': lead.expected_revenue,
                }
                for lead in opportunities
            ],
            'recent_events': [
                {
                    'type': self._event_type_label(event.event_type),
                    'old_value': event.old_value or None,
                    'new_value': event.new_value or None,
                    'detected_at': fields.Date.to_string(event.detected_at),
                }
                for event in recent
            ],
        }
