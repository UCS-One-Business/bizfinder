# -*- coding: utf-8 -*-

from odoo import fields, models


class BizfinderIndustry(models.Model):
    """Curated industry shortcut. Each industry maps to one or more SNI
    prefixes that get OR'd into the SNI_PREFIX filter at search time."""
    _name = 'bizfinder.industry'
    _description = 'Bizfinder industry shortcut'
    _order = 'sequence, name'

    name = fields.Char(string='Industry', required=True, translate=True)
    sequence = fields.Integer(default=10)
    sni_prefixes = fields.Char(
        string='SNI prefixes',
        required=True,
        help="Comma-separated SNI prefixes (e.g. '41,43' for construction).",
    )

    def expand_prefixes(self) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for rec in self:
            for raw in (rec.sni_prefixes or '').split(','):
                p = raw.strip()
                if p and p not in seen:
                    seen.add(p)
                    out.append(p)
        return out
