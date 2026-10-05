

from odoo import api, fields, models


class BizfinderRevealConfirm(models.TransientModel):
    _name = 'bizfinder.reveal.confirm'
    _description = 'Bizfinder Reveal Billing Confirmation'

    wizard_id = fields.Many2one('bizfinder.search', required=True, ondelete='cascade')
    reveal_count = fields.Integer(string='Billable reveals', readonly=True)
    price_per_reveal = fields.Float(string='Price per reveal', readonly=True)
    currency = fields.Char(readonly=True)
    estimated_total = fields.Float(
        string='Estimated total',
        compute='_compute_estimated_total',
    )
    # Single-field "amount + currency" readout for the compact confirm modal,
    # e.g. "340.00 SEK" (currency here is a plain Char from the billing API,
    # not a res.currency, so the monetary widget can't be used).
    estimated_total_display = fields.Char(
        string='Total price',
        compute='_compute_estimated_total',
    )

    @api.depends('reveal_count', 'price_per_reveal', 'currency')
    def _compute_estimated_total(self):
        for rec in self:
            rec.estimated_total = rec.reveal_count * rec.price_per_reveal
            rec.estimated_total_display = "%.2f %s" % (
                rec.estimated_total, rec.currency or '')

    def action_confirm(self):
        self.ensure_one()
        return self.wizard_id.with_context(bizfinder_billing_confirmed=True).action_create_leads()
