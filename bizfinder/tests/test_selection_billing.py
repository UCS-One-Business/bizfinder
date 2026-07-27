
"""Selection + billing-estimate behaviour of the Bizfinder search wizard.

Covers:

* ``bizfinder.search.action_select_all`` / ``action_deselect_all`` -- the
  native one-shot (de)select buttons (``bizfinder_search.py`` L169-176);
* ``bizfinder.search._compute_billing_estimate`` -- ``selected_reveal_count``
  and ``estimated_reveal_total`` derived from the selected result lines and the
  per-reveal price (L102-107); and
* ``bizfinder.reveal.confirm._compute_estimated_total`` -- the billing-dialog
  total (L593-596).

All tests are pure ORM except the two where-noted ones that drive
``_refresh_billing_pricing`` through ``self.mock_client`` / ``self._run_search``
so no real HTTP request is ever made.
"""

from odoo.tests import tagged

from .common import BizfinderTestCommon


@tagged('post_install', '-at_install')
class TestSelectionBilling(BizfinderTestCommon):
    """Selection toggles and the billing-estimate computes."""

    # ----------------------------------------------------------- helpers
    def _add_lines(self, wizard, selected_states):
        """Attach one ``bizfinder.result.line`` per entry in ``selected_states``
        (a list of booleans) to ``wizard``. Returns the created recordset.

        Org numbers are distinct but otherwise arbitrary -- nothing in these
        pure-ORM tests deduplicates them against crm.lead.
        """
        Line = self.env['bizfinder.result.line']
        return Line.create([{
            'wizard_id': wizard.id,
            'name': 'Prospect %d AB' % idx,
            'organisation_number': '55600000%02d' % idx,
            'selected': state,
        } for idx, state in enumerate(selected_states, start=1)])

    # ------------------------------------------------ select / deselect all
    def test_select_all_selects_every_result_line(self):
        """action_select_all flips every row on regardless of prior state."""
        wizard = self._new_wizard()
        self._add_lines(wizard, [False, True, False])

        wizard.action_select_all()

        self.assertTrue(
            all(wizard.result_line_ids.mapped('selected')),
            "every result line should be selected after select-all",
        )
        self.assertEqual(wizard.selected_reveal_count, 3)
        self.assertEqual(len(self._selected_lines(wizard)), 3)

    def test_deselect_all_clears_every_result_line(self):
        """action_deselect_all clears every row and collapses the estimate."""
        wizard = self._new_wizard(price_per_reveal=9.5)
        self._add_lines(wizard, [True, True, True])

        wizard.action_deselect_all()

        self.assertFalse(
            any(wizard.result_line_ids.mapped('selected')),
            "no result line should remain selected after deselect-all",
        )
        self.assertEqual(wizard.selected_reveal_count, 0)
        # count * price collapses to zero even though the price is non-zero.
        self.assertEqual(wizard.estimated_reveal_total, 0.0)

    def test_select_all_on_empty_results_is_noop(self):
        """With no result lines (search never run) both buttons are no-ops."""
        wizard = self._new_wizard()
        self.assertFalse(wizard.result_line_ids)

        # ensure_one passes on the single wizard; writing to an empty
        # result_line_ids recordset does nothing and must not raise.
        wizard.action_select_all()
        wizard.action_deselect_all()

        self.assertEqual(wizard.selected_reveal_count, 0)
        self.assertEqual(wizard.estimated_reveal_total, 0.0)

    # ------------------------------------------------- _compute_billing_estimate
    def test_billing_estimate_counts_only_selected_lines(self):
        """selected_reveal_count counts only the selected subset, and the
        estimate multiplies that count by the price."""
        wizard = self._new_wizard(price_per_reveal=9.5)
        lines = self._add_lines(wizard, [False, False, False])
        # Select exactly two of the three lines.
        (lines[0] | lines[2]).selected = True

        self.assertEqual(wizard.selected_reveal_count, 2)
        # Non-trivial price proves it multiplies rather than just counts.
        self.assertAlmostEqual(wizard.estimated_reveal_total, 19.0, places=2)

    def test_billing_estimate_zero_when_nothing_selected(self):
        """No selection -> zero cost even though lines exist and price is set."""
        wizard = self._new_wizard(price_per_reveal=9.5)
        self._add_lines(wizard, [False, False, False])

        self.assertEqual(wizard.selected_reveal_count, 0)
        self.assertEqual(wizard.estimated_reveal_total, 0.0)

    def test_billing_estimate_recomputes_on_selection_change(self):
        """Toggling a line's `selected` re-triggers the @api.depends recompute."""
        wizard = self._new_wizard(price_per_reveal=9.5)
        lines = self._add_lines(wizard, [False, False, False])

        lines[0].selected = True
        self.assertEqual(wizard.selected_reveal_count, 1)
        self.assertAlmostEqual(wizard.estimated_reveal_total, 9.5, places=2)

        lines[0].selected = False
        self.assertEqual(wizard.selected_reveal_count, 0)
        self.assertEqual(wizard.estimated_reveal_total, 0.0)

    def test_billing_estimate_zero_price_yields_zero_total(self):
        """Pricing never loaded: selection is counted but cost stays zero."""
        wizard = self._new_wizard()  # price_per_reveal defaults to 0.0
        self._add_lines(wizard, [False, False, False])

        wizard.action_select_all()

        self.assertEqual(wizard.price_per_reveal, 0.0)
        self.assertEqual(wizard.selected_reveal_count, 3)
        # count * 0.0 -- displayed cost is zero until pricing is fetched.
        self.assertEqual(wizard.estimated_reveal_total, 0.0)

    # ------------------------------------ _refresh_billing_pricing integration
    def test_refresh_pricing_without_price_leaves_estimate_zero(self):
        """get_billing_pricing returning no pricePerReveal key -> price 0.0.

        Drives _refresh_billing_pricing (via action_search) with a payload that
        omits ``pricePerReveal``, exercising the
        ``float(pricing.get('pricePerReveal') or 0.0)`` guard (L269). The
        currency is still captured (L270).
        """
        wizard = self._run_search(pricing={'currency': 'SEK'})

        wizard.action_select_all()

        self.assertEqual(wizard.price_per_reveal, 0.0)
        self.assertEqual(wizard.billing_currency, 'SEK')
        self.assertEqual(wizard.returned_count, 3)
        self.assertEqual(wizard.selected_reveal_count, wizard.returned_count)
        # Full selection, but the pricing endpoint returned no price.
        self.assertEqual(wizard.estimated_reveal_total, 0.0)

    def test_select_all_then_estimate_uses_fetched_price(self):
        """Search pulls the real PRICING fixture; select-all then bills at it."""
        wizard = self._run_search()  # default fixtures: 3 rows + PRICING

        wizard.action_select_all()

        self.assertEqual(wizard.returned_count, 3)
        self.assertEqual(len(wizard.result_line_ids), 3)
        self.assertEqual(wizard.price_per_reveal, 9.5)
        self.assertEqual(wizard.billing_currency, 'SEK')
        self.assertEqual(wizard.selected_reveal_count, 3)
        self.assertAlmostEqual(wizard.estimated_reveal_total, 28.5, places=2)

    # ----------------------------- bizfinder.reveal.confirm._compute_estimated_total
    def test_reveal_confirm_estimated_total_multiplies(self):
        """The confirm dialog's estimated_total is reveal_count * price."""
        wizard = self._new_wizard()
        confirm = self.env['bizfinder.reveal.confirm'].create({
            'wizard_id': wizard.id,
            'reveal_count': 4,
            'price_per_reveal': 9.5,
            'currency': 'SEK',
        })

        self.assertAlmostEqual(confirm.estimated_total, 38.0, places=2)
        self.assertEqual(confirm.reveal_count, 4)
        self.assertEqual(confirm.currency, 'SEK')

    def test_reveal_confirm_zero_count_yields_zero_total(self):
        """Nothing left to reveal -> the dialog shows no billable cost."""
        wizard = self._new_wizard()
        confirm = self.env['bizfinder.reveal.confirm'].create({
            'wizard_id': wizard.id,
            'reveal_count': 0,
            'price_per_reveal': 9.5,
            'currency': 'SEK',
        })

        self.assertEqual(confirm.estimated_total, 0.0)

    def test_reveal_confirm_recomputes_on_count_change(self):
        """Changing reveal_count re-triggers the @api.depends recompute."""
        wizard = self._new_wizard()
        confirm = self.env['bizfinder.reveal.confirm'].create({
            'wizard_id': wizard.id,
            'reveal_count': 2,
            'price_per_reveal': 9.5,
            'currency': 'SEK',
        })

        self.assertAlmostEqual(confirm.estimated_total, 19.0, places=2)

        confirm.reveal_count = 5
        self.assertAlmostEqual(confirm.estimated_total, 47.5, places=2)
