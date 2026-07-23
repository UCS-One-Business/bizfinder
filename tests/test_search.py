
"""Tests for ``bizfinder.search.action_search`` (the "action_search" cluster).

Every external ``bizfinder.client`` call is mocked through
``BizfinderTestCommon.mock_client`` so these tests never touch the network.
Assertions are traced to the real source in
``src/bizfinder/wizards/bizfinder_search.py``:

* the camelCase -> ORM mapping that builds ``bizfinder.result.line`` records
  (action_search lines ~205-245);
* the dedup against ``crm.lead.company_organisation_number`` (lines ~193-201);
* the counters ``hit_count`` / ``returned_count`` / ``duplicate_count``
  (lines ~246-248);
* the "no results" notification branch (lines ~250-264); and
* ``_refresh_billing_pricing`` (lines ~266-270) and the paging contract
  ``client.search(values, skip=0, take=PAGE_SIZE)`` with ``PAGE_SIZE == 200``.
"""

from datetime import date

from odoo.tests import tagged

from .common import BizfinderTestCommon


@tagged('post_install', '-at_install')
class TestBizfinderActionSearch(BizfinderTestCommon):

    # ------------------------------------------------------------- happy path

    def test_search_creates_result_lines_from_rows(self):
        """Fresh wizard, no pre-existing leads: one result line per row, the
        counters reflect zero dedup, and nothing is returned (no notification)."""
        wizard = self._new_wizard()
        with self.mock_client():  # 3 sample rows, preview == DEFAULT_HIT_COUNT (3)
            result = wizard.action_search()

        self.assertEqual(len(wizard.result_line_ids), 3)
        self.assertEqual(wizard.hit_count, self.DEFAULT_HIT_COUNT)
        self.assertEqual(wizard.hit_count, 3)
        self.assertEqual(wizard.returned_count, 3)
        self.assertEqual(wizard.duplicate_count, 0)
        # Rows produced -> action_search returns None (no display_notification).
        self.assertFalse(result)
        self.assertEqual(
            set(wizard.result_line_ids.mapped('organisation_number')),
            set(self.ORG_NUMBERS),
        )

    def test_search_maps_camelcase_fields_onto_result_line(self):
        """The explicit camelCase->ORM mapping for a fully-populated row covers
        every field type (Char/Float/Integer/Date/Boolean)."""
        wizard = self._run_search()
        line = wizard.result_line_ids.filtered(
            lambda l: l.organisation_number == '5566778899')
        self.assertEqual(len(line), 1)

        # Char
        self.assertEqual(line.name, 'Nordfält Bygg AB')
        self.assertEqual(line.vat_number, 'SE556677889901')
        self.assertEqual(line.phone, '+46 8 123 45 67')
        # Float
        self.assertEqual(line.net_sales, 42150.0)
        self.assertEqual(line.operating_result, 3120.0)
        self.assertEqual(line.growth_pct, 18.4)
        # Integer
        self.assertEqual(line.number_of_units, 2)
        # legalEntityText wins over legalEntity
        self.assertEqual(line.legal_entity, 'Aktiebolag')
        # Date parsed from the 'accountDateTo' string
        self.assertEqual(line.account_date_to, date(2025, 12, 31))
        # Boolean
        self.assertIs(line.accountant_obligation, True)

    def test_search_legal_entity_falls_back_to_legal_entity_code(self):
        """`r.get('legalEntityText') or r.get('legalEntity')`: when the
        preferred text is empty, the secondary code is used."""
        rows = self.sample_search_rows()[:1]
        rows[0]['legalEntityText'] = ''  # blank -> falls back to legalEntity ('AB')
        wizard = self._run_search(search=rows, preview=1)

        self.assertEqual(len(wizard.result_line_ids), 1)
        self.assertEqual(wizard.result_line_ids.legal_entity, 'AB')

    def test_search_missing_keys_default_safely(self):
        """A sparse row (only organisationNumber) exercises every `or` default:
        name -> '(unknown)', numeric -> 0/0.0, date -> False, char -> ''."""
        wizard = self._run_search(
            search=[{'organisationNumber': '5500000001'}], preview=1)

        self.assertEqual(len(wizard.result_line_ids), 1)
        line = wizard.result_line_ids
        self.assertEqual(line.name, '(unknown)')
        self.assertEqual(line.net_sales, 0.0)
        self.assertEqual(line.number_of_units, 0)
        self.assertIs(line.account_date_to, False)
        # Char default is '' (an empty string is preserved by the ORM, not False).
        self.assertEqual(line.phone, '')

    # ----------------------------------------------------------------- dedup

    def test_search_dedupes_existing_leads(self):
        """One crm.lead already exists for ORG_NUMBERS[0]: its row is dropped
        before lines are built, the counters reflect the drop, and hit_count
        stays at the API total (not reduced by dedup)."""
        self.env['crm.lead'].create({
            'name': 'Existing',
            'company_organisation_number': self.ORG_NUMBERS[0],
        })

        wizard = self._run_search()  # 3 rows, preview -> 3

        self.assertEqual(len(wizard.result_line_ids), 2)
        self.assertEqual(wizard.duplicate_count, 1)
        self.assertEqual(wizard.returned_count, 2)
        self.assertEqual(wizard.hit_count, 3)

        orgs = set(wizard.result_line_ids.mapped('organisation_number'))
        self.assertNotIn(self.ORG_NUMBERS[0], orgs)
        self.assertIn(self.ORG_NUMBERS[1], orgs)
        self.assertIn(self.ORG_NUMBERS[2], orgs)

    def test_search_rows_without_org_number_survive_dedup(self):
        """A row with no organisationNumber is never matched against crm.lead
        and must always be kept -- even when a seeded lead dedups the other row,
        and with no crash from the empty/absent org in the search domain."""
        rows = self.sample_search_rows()
        full_row = rows[0]                         # org 5566778899
        orgless_row = rows[1]
        orgless_row.pop('organisationNumber', None)

        # Seed a lead matching the FULL row, so dedup actively drops it and only
        # the org-less row can survive.
        self.env['crm.lead'].create({
            'name': 'Existing',
            'company_organisation_number': full_row['organisationNumber'],
        })

        wizard = self._run_search(search=[full_row, orgless_row], preview=2)

        # The org-less row survived; the full (seeded) row was deduped.
        self.assertEqual(len(wizard.result_line_ids), 1)
        self.assertEqual(wizard.result_line_ids.organisation_number, '')
        self.assertEqual(wizard.returned_count, 1)
        self.assertEqual(wizard.duplicate_count, 1)

    # --------------------------------------------------------- no-result paths

    def test_search_all_duplicates_returns_already_in_crm_notification(self):
        """Every returned row is already a crm.lead and preview total > 0:
        result lines are wiped and the 'already in your CRM' warning returns."""
        for org in self.ORG_NUMBERS:
            self.env['crm.lead'].create({
                'name': 'Existing %s' % org,
                'company_organisation_number': org,
            })

        wizard = self._new_wizard()
        with self.mock_client(preview=3):  # default 3 rows, all duplicates
            result = wizard.action_search()

        self.assertIsInstance(result, dict)
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        params = result['params']
        self.assertEqual(
            params['message'],
            'The companies that matched are already in your CRM.')
        self.assertEqual(params['title'], 'No results')
        self.assertEqual(params['type'], 'warning')
        self.assertFalse(params['sticky'])

        self.assertFalse(wizard.result_line_ids)
        self.assertEqual(wizard.returned_count, 0)
        self.assertEqual(wizard.duplicate_count, 3)
        self.assertEqual(wizard.hit_count, 3)

    def test_search_no_matches_returns_no_companies_notification(self):
        """The API returns zero rows and total == 0: the 'No companies matched'
        warning returns and every counter is zeroed."""
        wizard = self._new_wizard()
        with self.mock_client(search=[], preview=0):
            result = wizard.action_search()

        self.assertIsInstance(result, dict)
        self.assertEqual(result['type'], 'ir.actions.client')
        self.assertEqual(result['tag'], 'display_notification')
        params = result['params']
        self.assertEqual(
            params['message'],
            'No companies matched your filters. Try widening them.')
        self.assertEqual(params['title'], 'No results')
        self.assertEqual(params['type'], 'warning')

        self.assertFalse(wizard.result_line_ids)
        self.assertEqual(wizard.hit_count, 0)
        self.assertEqual(wizard.returned_count, 0)
        self.assertEqual(wizard.duplicate_count, 0)

    # -------------------------------------------------------------- billing

    def test_search_refreshes_billing_pricing(self):
        """action_search pulls price_per_reveal / billing_currency live from
        get_billing_pricing() on each run (non-default payload proves it)."""
        wizard = self._run_search(
            pricing={'pricePerReveal': 12.25, 'currency': 'EUR'}, preview=3)

        self.assertEqual(wizard.price_per_reveal, 12.25)
        self.assertEqual(wizard.billing_currency, 'EUR')
        # Sanity: lines are still built alongside the pricing refresh.
        self.assertEqual(len(wizard.result_line_ids), 3)

    def test_search_billing_pricing_missing_keys_default_to_zero_and_blank(self):
        """An empty pricing dict coerces via `float(... or 0.0)` and `... or ''`
        rather than raising or storing None."""
        wizard = self._run_search(pricing={}, preview=3)

        self.assertEqual(wizard.price_per_reveal, 0.0)
        self.assertEqual(wizard.billing_currency, '')

    # --------------------------------------------------------- rerun / paging

    def test_search_rerun_replaces_previous_result_lines(self):
        """Re-running unlinks the prior result lines and rebuilds from the new
        payload; counters are recomputed, not accumulated."""
        wizard = self._run_search()  # 3 rows
        self.assertEqual(len(wizard.result_line_ids), 3)

        new_row = {'name': 'Helt Ny AB', 'organisationNumber': '5500000099'}
        self._run_search(wizard=wizard, search=[new_row], preview=1)

        self.assertEqual(len(wizard.result_line_ids), 1)
        self.assertEqual(wizard.result_line_ids.organisation_number, '5500000099')
        self.assertEqual(wizard.returned_count, 1)

    def test_search_hit_count_reflects_total_beyond_returned_page(self):
        """preview() reports more than the returned page: hit_count tracks the
        API total while returned_count reflects only materialised rows."""
        wizard = self._new_wizard()
        with self.mock_client(preview=500):  # default 3 rows returned
            result = wizard.action_search()

        self.assertEqual(wizard.hit_count, 500)
        self.assertEqual(wizard.returned_count, 3)
        self.assertEqual(wizard.duplicate_count, 0)
        self.assertEqual(len(wizard.result_line_ids), 3)
        self.assertFalse(result)  # rows exist -> no notification

    def test_search_forwards_skip_zero_and_page_size_take(self):
        """action_search calls client.search(values, skip=0, take=PAGE_SIZE).
        Capture the call args and assert the paging contract (PAGE_SIZE == 200)
        that the billing assumptions depend on."""
        calls = []

        def recording_search(_model, *args, **kwargs):
            calls.append((args, kwargs))
            return self.sample_search_rows()

        wizard = self._new_wizard()
        with self.mock_client(search=recording_search, preview=3):
            wizard.action_search()

        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(kwargs.get('skip'), 0)
        self.assertEqual(kwargs.get('take'), 200)
        self.assertEqual(kwargs.get('take'), wizard.PAGE_SIZE)
        # First positional arg is the _build_values() payload: a non-None list.
        self.assertEqual(len(args), 1)
        self.assertIsNotNone(args[0])
        self.assertIsInstance(args[0], list)
