# -*- coding: utf-8 -*-
"""Drop the old server-action entry point.

The menu entry point changes from an ir.actions.server (returning an ad-hoc
act_window) to a real ir.actions.act_window. The new action reuses the
``bizfinder`` URL path, which is globally unique, so the old server action must
be removed before the new record is created.
"""

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    old = env.ref('bizfinder.action_bizfinder_search_open', raise_if_not_found=False)
    if old:
        old.unlink()
