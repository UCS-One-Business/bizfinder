
"""Preset-lifecycle behaviour of the Bizfinder search wizard.

Covers the four preset buttons on ``bizfinder.search`` plus the save dialog and
the onchange hook -- i.e. how a rep creates, applies, updates, clears and
re-uses saved company-search filter sets:

* ``bizfinder.search.action_update_preset`` -- overwrite the linked preset with
  the current filters, or refuse when none is selected
  (``bizfinder_search.py`` L134-151);
* ``bizfinder.search.action_clear_preset`` -- detach the preset, keep the
  filters (L153-156);
* ``bizfinder.search.action_manage_presets`` -- the crash-guard that returns a
  fully-resolved act_window with a ``views`` key (L158-165);
* ``bizfinder.preset.save.action_save`` -- snapshot the wizard filters onto a
  new preset and link it back (L611-628), including the
  ``unique(name, company_id)`` constraint on ``bizfinder.preset``
  (``bizfinder_preset.py`` L86-89); and
* ``bizfinder.search._onchange_preset_id`` -- apply a preset's saved filters,
  with the documented early-return when the preset is cleared (L111-119).

None of these paths touch ``bizfinder.client`` (no search / preview / reveal /
get_billing_pricing), so no HTTP mocking is required -- but the tests still build
on :class:`BizfinderTestCommon` for its ``_new_wizard`` helper and post-install
tags.
"""

import psycopg2
from odoo.exceptions import UserError
from odoo.tests import Form, tagged
from odoo.tools import mute_logger

from .common import BizfinderTestCommon


@tagged('post_install', '-at_install')
class TestPresetLifecycle(BizfinderTestCommon):
    """Create / apply / update / clear / manage saved filter presets."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The wizard's region picker is fed by the seeded bizfinder.region
        # records (data/bizfinder_region_data.xml). Two distinct ones are
        # enough to prove the "current filters win" overwrite semantics; their
        # integer ``code`` round-trips through POST_REGION_CODE.
        regions = cls.env['bizfinder.region'].search([], limit=2)
        assert len(regions) >= 2, (
            "bizfinder.region seed data must provide at least two regions"
        )
        cls.region_a = regions[0]
        cls.region_b = regions[1]

    # --------------------------------------------------------------- update
    def test_update_preset_without_selection_raises(self):
        """action_update_preset on a wizard with no preset selected must refuse
        loudly (UserError) rather than silently no-op -- bizfinder_search.py
        L138-139."""
        wizard = self._new_wizard()  # preset_id unset
        self.assertFalse(wizard.preset_id)

        count_before = self.env['bizfinder.preset'].search_count([])
        with self.assertRaises(UserError) as cm:
            wizard.action_update_preset()

        self.assertEqual(
            str(cm.exception),
            "Select a preset first, then update it.",
        )
        # No preset was created or modified as a side effect.
        self.assertEqual(
            self.env['bizfinder.preset'].search_count([]),
            count_before,
            "a failed update must not create or touch any preset",
        )

    def test_update_preset_overwrites_filters_and_returns_success_notification(self):
        """With a preset linked, action_update_preset snapshots the wizard's
        CURRENT filters onto it (overwriting whatever was stored) and returns a
        success display_notification -- bizfinder_search.py L140-151."""
        # Preset starts pointing at region_b ...
        preset = self.env['bizfinder.preset'].create({
            'name': 'P1',
            'region_ids': [(6, 0, self.region_b.ids)],
        })
        # ... the wizard at region_a. A plain create does NOT fire
        # _onchange_preset_id, so the wizard keeps region_a (not the preset's
        # region_b) -- exactly the divergence action_update_preset reconciles.
        wizard = self._new_wizard(
            region_ids=[(6, 0, self.region_a.ids)],
            preset_id=preset.id,
        )

        action = wizard.action_update_preset()

        # Current filters won: region_b was overwritten with region_a via the
        # preset.write(_resolve_filters_to_vals(self._build_values())) round-trip
        # through POST_REGION_CODE.
        self.assertEqual(preset.region_ids, self.region_a)
        self.assertNotIn(self.region_b, preset.region_ids)

        # Returned action is the success toast.
        self.assertEqual(action['type'], 'ir.actions.client')
        self.assertEqual(action['tag'], 'display_notification')
        params = action['params']
        self.assertEqual(params['type'], 'success')
        self.assertEqual(params['title'], 'Preset updated')
        self.assertEqual(
            params['message'],
            "'P1' now matches the current filters.",
        )
        self.assertFalse(params['sticky'])

    # ---------------------------------------------------------------- clear
    def test_clear_preset_detaches_link_but_keeps_filters(self):
        """action_clear_preset detaches the preset only; the filters the user
        already chose stay put -- bizfinder_search.py L155-156."""
        preset = self.env['bizfinder.preset'].create({'name': 'P2'})
        wizard = self._new_wizard(
            region_ids=[(6, 0, self.region_a.ids)],
            zip_prefixes='112',
            preset_id=preset.id,
        )

        wizard.action_clear_preset()

        self.assertFalse(wizard.preset_id, "the preset link must be cleared")
        # Filters survive the detach.
        self.assertEqual(wizard.region_ids, self.region_a)
        self.assertEqual(wizard.zip_prefixes, '112')
        # Clearing the link does not delete the preset record itself.
        self.assertEqual(
            self.env['bizfinder.preset'].search_count([('name', '=', 'P2')]),
            1,
        )

    # --------------------------------------------------------------- manage
    def test_manage_presets_returns_fully_resolved_act_window(self):
        """Regression guard for the historical 'Manage presets crash':
        action_manage_presets must return a fully-resolved act_window (with a
        ``views`` key the web client can .map over), not a bare dict --
        bizfinder_search.py L164-165."""
        wizard = self._new_wizard()

        action = wizard.action_manage_presets()

        self.assertIsInstance(action, dict)
        self.assertEqual(action['type'], 'ir.actions.act_window')
        # The explicit crash guard: a bare dict without 'views' makes the web
        # client's action preprocessing blow up on action.views.map.
        self.assertIn('views', action)
        self.assertTrue(
            action['views'],
            "act_window must carry a non-empty views list",
        )
        self.assertEqual(action['res_model'], 'bizfinder.preset')

    # ----------------------------------------------------------------- save
    def test_save_preset_creates_snapshots_filters_and_links_back(self):
        """bizfinder.preset.save.action_save creates a preset, snapshots the
        wizard filters onto it, links it back as wizard.preset_id and returns an
        act_window targeting the wizard -- bizfinder_search.py L613-628."""
        wizard = self._new_wizard(region_ids=[(6, 0, self.region_a.ids)])
        save = self.env['bizfinder.preset.save'].create({
            'wizard_id': wizard.id,
            'name': 'My preset',
            'description': 'desc',
        })

        action = save.action_save()

        # A new preset exists and is linked back onto the wizard (L619).
        preset = self.env['bizfinder.preset'].search([('name', '=', 'My preset')])
        self.assertEqual(len(preset), 1)
        self.assertEqual(wizard.preset_id, preset)
        self.assertEqual(wizard.preset_id.description, 'desc')
        # The filter snapshot round-trips: region_a survives encode -> decode
        # (preset.write(_resolve_filters_to_vals(wizard._build_values())), L618).
        self.assertEqual(wizard.preset_id.region_ids, self.region_a)

        # Returned action re-opens the wizard.
        self.assertEqual(action['res_model'], 'bizfinder.search')
        self.assertEqual(action['res_id'], wizard.id)
        self.assertEqual(action['target'], 'current')
        self.assertIn('views', action)

    def test_save_preset_duplicate_name_raises_unique_constraint(self):
        """Saving a preset whose name already exists for the company is rejected
        by the unique(name, company_id) SQL constraint rather than creating a
        duplicate -- bizfinder_preset.py L86-89."""
        # Pre-existing preset for the current company (company_id defaults to
        # env.company on both records, so the names collide).
        self.env['bizfinder.preset'].create({'name': 'Dup'})
        wizard = self._new_wizard()
        save = self.env['bizfinder.preset.save'].create({
            'wizard_id': wizard.id,
            'name': 'Dup',
        })

        # The collision surfaces at flush; wrap in a savepoint so the failed
        # flush does not poison the test cursor, and mute the SQL logger.
        with self.assertRaises(psycopg2.IntegrityError), \
                mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            save.action_save()
            self.env.flush_all()

        # The savepoint rolled the partial work back without committing the
        # cache; drop it before asserting on the persisted state.
        self.env.invalidate_all()
        self.assertFalse(
            wizard.preset_id,
            "the failed save must not leave a partial preset link",
        )
        self.assertEqual(
            self.env['bizfinder.preset'].search_count([('name', '=', 'Dup')]),
            1,
            "the duplicate must not have been created",
        )

    # ------------------------------------------------------------- onchange
    def test_onchange_preset_id_applies_preset_filters(self):
        """Selecting a preset applies its saved filters via _onchange_preset_id.
        Driven through Form so the onchange actually fires --
        bizfinder_search.py L117-119."""
        preset = self.env['bizfinder.preset'].create({
            'name': 'Applied',
            'region_ids': [(6, 0, self.region_a.ids)],
        })

        form = Form(self.env['bizfinder.search'])
        form.preset_id = preset

        # The onchange decoded the preset's filters onto the wizard's own
        # fields (region_ids is exposed as an M2MProxy, so compare on ids).
        self.assertEqual(form.region_ids.ids, self.region_a.ids)

        wizard = form.save()
        self.assertEqual(wizard.region_ids, self.region_a)
        self.assertEqual(wizard.preset_id, preset)

    def test_onchange_clearing_preset_keeps_current_filters(self):
        """Documented edge of _onchange_preset_id: clearing the preset returns
        early (L115-116) and leaves the already-applied filters in place --
        distinct from the action_clear_preset button path."""
        preset = self.env['bizfinder.preset'].create({
            'name': 'Tmp',
            'region_ids': [(6, 0, self.region_a.ids)],
        })

        form = Form(self.env['bizfinder.search'])
        form.preset_id = preset  # applies region_a
        self.assertEqual(form.region_ids.ids, self.region_a.ids)

        # Clear the picker -> the onchange early-returns and must NOT wipe the
        # filters it previously applied.
        form.preset_id = self.env['bizfinder.preset']

        self.assertEqual(form.region_ids.ids, self.region_a.ids)
        self.assertFalse(form.preset_id)
