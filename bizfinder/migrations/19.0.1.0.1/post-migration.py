"""Drop the legacy act_window action.

The CRM > Prospect menu was originally wired to
``action_bizfinder_search`` (an ``ir.actions.act_window``). It now
points to ``action_bizfinder_search_open`` (a server action that
pre-creates the wizard record so the URL lands on a real ``res_id``).

This migration removes the orphaned act_window row and its ir_model_data
entry so the database matches the source.
"""


def migrate(cr, version):
    # migration-lint: allow-unguarded -- ir_act_window/ir_model_data are core
    # Odoo tables, always present when a migration runs.
    cr.execute(
        """
        DELETE FROM ir_act_window
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'bizfinder'
               AND name = 'action_bizfinder_search'
               AND model = 'ir.actions.act_window'
         );
        """
    )
    # migration-lint: allow-unguarded -- core table, see above.
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'bizfinder'
           AND name = 'action_bizfinder_search'
           AND model = 'ir.actions.act_window';
        """
    )
