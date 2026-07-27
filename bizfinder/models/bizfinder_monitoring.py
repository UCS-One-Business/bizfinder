
import logging
from datetime import datetime, timedelta

from odoo import _, api, fields, models

from .res_partner import BATCH_SIZE

_logger = logging.getLogger(__name__)

# Known event types and their human labels. event_type is deliberately a raw
# Char (not a Selection): the API may grow new types and an unknown type must
# still be stored and shown, not crash the nightly cron. Unknown types render
# via a title-cased fallback in _event_type_label.
EVENT_TYPE_LABELS = {
    'STATUS_CHANGED': 'Status changed',
    'F_TAX_LOST': 'F-tax lost',
    'F_TAX_GAINED': 'F-tax gained',
    'MOMS_LOST': 'VAT registration (moms) lost',
    'MOMS_GAINED': 'VAT registration (moms) gained',
    'NAME_CHANGED': 'Name changed',
    'ADDRESS_CHANGED': 'Address changed',
    'PHONE_CHANGED': 'Phone changed',
    'DIRECTOR_CHANGED': 'Director changed',
}

# Always-severe types. STATUS_CHANGED is severe only when the partner is no
# longer active after the status sync (see _is_severe).
SEVERE_EVENT_TYPES = {'F_TAX_LOST', 'MOMS_LOST'}

EVENTS_LAST_PULL_PARAM = 'bizfinder.events_last_pull'
FIRST_PULL_LOOKBACK_DAYS = 30


class BizfinderCompanyEvent(models.Model):
    _name = 'bizfinder.company.event'
    _description = 'Bizfinder Company Event'
    _order = 'detected_at desc'

    partner_id = fields.Many2one('res.partner', string='Company', ondelete='cascade', index=True)
    org_number = fields.Char(string='Org number', required=True, index=True)
    company_name = fields.Char(string='Company name')
    event_type = fields.Char(required=True)
    event_type_label = fields.Char(compute='_compute_event_type_label')
    old_value = fields.Char()
    new_value = fields.Char()
    detected_at = fields.Datetime(required=True)

    _org_event_detected_uniq = models.Constraint(
        'unique(org_number, event_type, detected_at)',
        'This Bizfinder event was already imported.',
    )

    @api.model
    def _event_type_label(self, event_type: str) -> str:
        label = EVENT_TYPE_LABELS.get(event_type)
        if label:
            return label
        return (event_type or '').replace('_', ' ').capitalize()

    def _compute_event_type_label(self):
        for event in self:
            event.event_type_label = self._event_type_label(event.event_type)

    # ------------------------------------------------------------------ cron
    @api.model
    def cron_sync_monitoring(self):
        """Daily monitoring sync: refresh registry status/financials for the
        monitored customer base, then pull change events and surface them as
        event rows + chatter (+ activities for severe events).

        Per-batch failures are logged and the remaining batches still run, but
        if every batch failed the last error is re-raised so the cron shows up
        red instead of silently doing nothing (AGENTS.md: loud failures).
        """
        Partner = self.env['res.partner'].sudo()
        monitored = Partner.search([
            ('bizfinder_monitored', '=', True),
            ('is_company', '=', True),
            ('company_registry', '!=', False),
        ])
        org_map = monitored._bizfinder_org_map()
        if not org_map:
            return
        since = self._events_since()
        orgs = list(org_map)
        newest_seen = None
        failures, successes = [], 0
        for start in range(0, len(orgs), BATCH_SIZE):
            batch_orgs = orgs[start:start + BATCH_SIZE]
            batch_partners = Partner.browse([org_map[o].id for o in batch_orgs])
            try:
                batch_partners.bizfinder_sync_status()
                batch_newest = self._pull_events(batch_orgs, org_map, since)
                if batch_newest and (not newest_seen or batch_newest > newest_seen):
                    newest_seen = batch_newest
                successes += 1
            except Exception as exc:
                _logger.exception(
                    "bizfinder: monitoring sync failed for batch starting at org %s",
                    batch_orgs[0])
                failures.append(exc)
        if newest_seen:
            self.env['ir.config_parameter'].sudo().set_param(
                EVENTS_LAST_PULL_PARAM, newest_seen)
        if failures and not successes:
            raise failures[-1]

    @api.model
    def _events_since(self) -> str:
        since = self.env['ir.config_parameter'].sudo().get_param(EVENTS_LAST_PULL_PARAM)
        if not since:
            since = (
                datetime.utcnow() - timedelta(days=FIRST_PULL_LOOKBACK_DAYS)
            ).strftime('%Y-%m-%dT%H:%M:%SZ')
        return since

    @api.model
    def _parse_detected_at(self, value: str) -> datetime:
        """ISO datetime (possibly Z-suffixed / offset-aware) -> naive UTC,
        which is what the ORM stores in Datetime fields."""
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo:
            dt = (dt - dt.utcoffset()).replace(tzinfo=None)
        return dt

    @api.model
    def _pull_events(self, batch_orgs: list[str], org_map: dict, since: str) -> str | None:
        """Fetch events for one org batch, create the new rows, notify.
        Returns the newest detectedAt ISO string seen (or None)."""
        rows = self.env['bizfinder.client'].events(batch_orgs, since=since)
        if not rows:
            return None
        Event = self.sudo()
        existing = {
            (e.org_number, e.event_type, e.detected_at)
            for e in Event.search([('org_number', 'in', batch_orgs)])
        }
        newest = None
        for row in rows:
            detected_raw = row['detectedAt']
            if not newest or detected_raw > newest:
                newest = detected_raw
            org = self.env['res.partner']._bizfinder_normalize_org(row.get('orgNumber'))
            detected_at = self._parse_detected_at(detected_raw)
            event_type = row.get('eventType') or ''
            key = (org, event_type, detected_at)
            if key in existing:
                continue
            existing.add(key)
            partner = org_map.get(org)
            event = Event.create({
                'partner_id': partner.id if partner else False,
                'org_number': org,
                'company_name': row.get('companyName') or '',
                'event_type': event_type,
                'old_value': row.get('oldValue') or '',
                'new_value': row.get('newValue') or '',
                'detected_at': detected_at,
            })
            if partner:
                event._notify_partner(partner)
        return newest

    # ------------------------------------------------------------- notifying
    def _is_severe(self, partner) -> bool:
        self.ensure_one()
        if self.event_type in SEVERE_EVENT_TYPES:
            return True
        # Status sync ran just before the event pull, so bizfinder_active
        # reflects the post-change state: a STATUS_CHANGED that left the
        # company inactive is severe, a change back to active is not.
        return self.event_type == 'STATUS_CHANGED' and not partner.bizfinder_active

    def _notify_partner(self, partner):
        """Post a chatter message on the partner; schedule a to-do activity
        for the partner's salesperson on severe events."""
        self.ensure_one()
        label = self._event_type_label(self.event_type)
        if self.old_value or self.new_value:
            body = _(
                "Bizfinder: %(label)s — %(old)s → %(new)s",
                label=label,
                old=self.old_value or _('(none)'),
                new=self.new_value or _('(none)'),
            )
        else:
            body = _("Bizfinder: %(label)s", label=label)
        partner.message_post(body=body)
        if self._is_severe(partner) and partner.user_id:
            partner.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_("Bizfinder alert: %(label)s", label=label),
                note=body,
                user_id=partner.user_id.id,
            )
