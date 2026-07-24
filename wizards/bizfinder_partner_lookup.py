
from odoo import _, fields, models
from odoo.exceptions import UserError


class BizfinderPartnerLookup(models.TransientModel):
    _name = 'bizfinder.partner.lookup'
    _description = 'Bizfinder Partner Lookup'

    query = fields.Char(
        string='Company name or org number',
        help="Digits match an organisation-number prefix, anything else "
             "matches the company name.",
    )
    partner_id = fields.Many2one(
        'res.partner', string='Partner to enrich', readonly=True,
        help="Set when the wizard was opened from an existing company; the "
             "picked result enriches this partner instead of creating a new one.")
    line_ids = fields.One2many('bizfinder.partner.lookup.line', 'wizard_id', string='Results')

    def action_search(self):
        self.ensure_one()
        if not self.query or len(self.query.strip()) < 2:
            raise UserError(_("Type at least two characters to search."))
        rows = self.env['bizfinder.client'].lookup(self.query.strip())
        self.line_ids.unlink()
        self.env['bizfinder.partner.lookup.line'].create([{
            'wizard_id': self.id,
            'name': r.get('name') or _('(unknown)'),
            'organisation_number': r.get('organisationNumber') or '',
            'city': r.get('city') or '',
            'legal_entity_text': r.get('legalEntityText') or '',
            'sni_text': r.get('sniText') or '',
            'employees': r.get('employees') or '',
        } for r in rows])
        if not rows:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Bizfinder'),
                    'message': _('No companies matched. Try a longer name or org number.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }
        return self._reopen()

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fetch from Bizfinder'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
        }


class BizfinderPartnerLookupLine(models.TransientModel):
    _name = 'bizfinder.partner.lookup.line'
    _description = 'Bizfinder Partner Lookup Result'

    wizard_id = fields.Many2one('bizfinder.partner.lookup', required=True, ondelete='cascade')
    name = fields.Char(string='Company', readonly=True)
    organisation_number = fields.Char(string='Org no.', readonly=True)
    city = fields.Char(readonly=True)
    legal_entity_text = fields.Char(string='Legal form', readonly=True)
    sni_text = fields.Char(string='Industry (SNI)', readonly=True)
    employees = fields.Char(readonly=True)

    def action_pick(self):
        """Write this result onto the wizard's partner (or create a new
        company partner), then run the per-partner Bizfinder status sync.

        Lookup results are redacted-tier: no street/phone. Only the org
        number, name and city come from the lookup; status and financials
        come from the follow-up sync. Existing partner values are never
        overwritten — only empty fields are filled.
        """
        self.ensure_one()
        partner = self.wizard_id.partner_id
        if partner:
            vals = {
                'is_company': True,
                'company_registry': self.organisation_number,
            }
            # Adopt the official registry name when the partner has none or
            # still carries the rough draft the user searched with; a real,
            # different name is never overwritten.
            query = (self.wizard_id.query or '').strip().lower()
            if not partner.name or partner.name.strip().lower() == query:
                vals['name'] = self.name
            if not partner.city and self.city:
                vals['city'] = self.city
            partner.write(vals)
        else:
            partner = self.env['res.partner'].create({
                'name': self.name,
                'is_company': True,
                'company_registry': self.organisation_number,
                'city': self.city or False,
            })
        partner.bizfinder_sync_status()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Company'),
            'res_model': 'res.partner',
            'res_id': partner.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
