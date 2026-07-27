
from odoo import fields, models


class BizfinderMagnitude(models.Model):
    """Coarse-grained user-facing magnitude band (Micro, Small, ...).

    Each magnitude expands into one or more API bucket keys (the literal
    Swedish enum strings the API expects). Modelled in Odoo rather than
    hardcoded on the wizard so admins can tune the band cuts without a
    code change.
    """
    _name = 'bizfinder.magnitude'
    _description = 'Bizfinder magnitude band'
    _order = 'kind, sequence, id'

    name = fields.Char(string='Label', required=True, translate=True)
    kind = fields.Selection(
        [('employees', 'Employees'), ('net_sales', 'Net sales')],
        required=True, index=True,
    )
    sequence = fields.Integer(default=10)
    bucket_keys = fields.Char(
        string='API bucket keys',
        required=True,
        help="Comma-separated API enum keys this magnitude expands to "
             "(e.g. '5-9 anställda,10-19 anställda').",
    )

    def expand_keys(self) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for rec in self:
            for raw in (rec.bucket_keys or '').split(','):
                key = raw.strip()
                if key and key not in seen:
                    seen.add(key)
                    out.append(key)
        return out
