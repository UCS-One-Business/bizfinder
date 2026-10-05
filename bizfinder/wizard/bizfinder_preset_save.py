

from odoo import _, fields, models


class BizfinderPresetSave(models.TransientModel):
    _name = 'bizfinder.preset.save'
    _description = 'Bizfinder Save Preset Dialog'

    wizard_id = fields.Many2one('bizfinder.search', required=True, ondelete='cascade')
    name = fields.Char(string='Preset name', required=True)
    description = fields.Text()

    def action_save(self):
        self.ensure_one()
        preset = self.env['bizfinder.preset'].create({
            'name': self.name,
            'description': self.description or False,
        })
        # Snapshot the wizard's current filters onto the new preset's fields.
        preset.write(
            preset._resolve_filters_to_vals(self.wizard_id._build_values()))
        self.wizard_id.preset_id = preset
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bizfinder Search'),
            'res_model': 'bizfinder.search',
            'res_id': self.wizard_id.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }
