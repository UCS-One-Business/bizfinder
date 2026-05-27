# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import AccessError


class BizfinderUsage(models.TransientModel):
    _name = 'bizfinder.usage'
    _description = 'Bizfinder Billing Usage'

    date_from = fields.Date(
        required=True,
        default=lambda self: fields.Date.start_of(fields.Date.today(), 'month'),
    )
    date_to = fields.Date(
        required=True,
        default=lambda self: fields.Date.end_of(fields.Date.today(), 'month'),
    )
    client_id = fields.Char(readonly=True)
    currency = fields.Char(readonly=True)
    reveals = fields.Integer(readonly=True)
    amount = fields.Float(readonly=True)

    @api.model
    def action_open_usage(self) -> dict:
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise AccessError(_("Only Sales managers can view Bizfinder billing usage."))
        rec = self.create({})
        rec.action_refresh()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bizfinder Usage'),
            'res_model': self._name,
            'res_id': rec.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_refresh(self):
        self.ensure_one()
        if not self.env.user.has_group('sales_team.group_sale_manager'):
            raise AccessError(_("Only Sales managers can view Bizfinder billing usage."))
        usage = self.env['bizfinder.client'].get_billing_usage(self.date_from, self.date_to)
        self.write({
            'client_id': usage.get('clientId') or '',
            'currency': usage.get('currency') or '',
            'reveals': int(usage.get('reveals') or 0),
            'amount': float(usage.get('amount') or 0.0),
        })
        return False
