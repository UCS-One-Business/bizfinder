
"""Shared test scaffolding for the Bizfinder search wizard.

The wizard (``bizfinder.search``) talks to an external FastAPI service through
the ``bizfinder.client`` AbstractModel. Tests must NEVER hit the network, so
this base class provides:

* a helper to build a usable ``bizfinder.search`` wizard record;
* realistic camelCase API payload fixtures (search rows, reveal rows, pricing)
  whose keys match exactly what ``action_search`` / ``action_create_leads`` /
  ``BizfinderSearch._format_notes`` actually read; and
* a ``mock_client`` context manager that patches every ``BizfinderClient``
  method the wizard calls (``search`` / ``preview`` / ``reveal`` /
  ``get_billing_pricing``) so no real HTTP request is ever made.

Subclasses should be decorated ``@tagged('post_install', '-at_install')`` and
import :class:`BizfinderTestCommon` from here.
"""

import copy
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

# Patch target for the external HTTP client. Patching the methods on this class
# is the documented mock pattern: the wizard resolves ``self.env['bizfinder.client']``
# whose registry class inherits these methods, so a ``patch.object`` here is
# seen by the wizard at call time.
from odoo.addons.bizfinder.models.bizfinder_client import BizfinderClient
from odoo.tests import TransactionCase, tagged

_UNSET = object()


@tagged('post_install', '-at_install')
class BizfinderTestCommon(TransactionCase):
    """Base TransactionCase for Bizfinder wizard tests.

    Provides wizard/builder helpers, sample API payloads and a ``mock_client``
    context manager. Decorated with the standard post-install tags so plain
    subclasses inherit them even if they forget to re-declare ``@tagged``.
    """

    # ------------------------------------------------------------------ data
    # Sample SEARCH rows -- one dict per company, camelCase keys exactly as the
    # /api/insight/prospects endpoint returns them and as ``action_search``
    # reads them (r.get('organisationNumber'), r.get('netSales'), ...). Org
    # numbers are deliberately distinct so the crm.lead
    # unique(company_organisation_number) constraint is never tripped.
    SEARCH_ROWS = [
        {
            'name': 'Nordfält Bygg AB',
            'organisationNumber': '5566778899',
            'vatNumber': 'SE556677889901',
            'phone': '+46 8 123 45 67',
            'fax': '+46 8 123 45 68',
            'address': 'Storgatan 1',
            'postCode': '11122',
            'city': 'Stockholm',
            'postCommunity': 'Stockholm',
            'visitingAddress': 'Storgatan 1',
            'visitingPostCode': '11122',
            'visitingCity': 'Stockholm',
            'visitingCommunity': 'Stockholm',
            'description': '41200 Byggande av bostadshus och andra byggnader',
            'employees': '10-19 anställda',
            'turnOver': '10 000-49 999 tkr',
            'legalEntityText': 'Aktiebolag',
            'legalEntity': 'AB',
            'numberOfUnits': 2,
            'netSales': 42150.0,
            'operatingResult': 3120.0,
            'netProfitLoss': 2480.0,
            'growthPct': 18.4,
            'headcountChangePct': 12.5,
            'solidityPct': 47.2,
            'operatingMarginPct': 7.4,
            'profitMarginPct': 5.9,
            'quickRatioPct': 132.0,
            'cashAtBank': 5600.0,
            'totalAssets': 28800.0,
            'totalEquity': 13600.0,
            'accountDateTo': '2025-12-31',
            'accountMonths': 12,
            'accountantObligation': True,
            'directorName': 'Anna Nordfält',
            'directorRole': 'VD',
            'registrationDate': '2011-03-14',
            'companyFormedDate': '2011-02-01',
            'statusDate': '2011-03-14',
        },
        {
            'name': 'Tjänstebolaget Väst AB',
            'organisationNumber': '5560123456',
            'vatNumber': 'SE556012345601',
            'phone': '+46 31 222 33 44',
            'fax': '',
            'address': 'Avenyn 12',
            'postCode': '41136',
            'city': 'Göteborg',
            'postCommunity': 'Göteborg',
            'visitingAddress': 'Avenyn 12',
            'visitingPostCode': '41136',
            'visitingCity': 'Göteborg',
            'visitingCommunity': 'Göteborg',
            'description': '62010 Dataprogrammering',
            'employees': '20-49 anställda',
            'turnOver': '50 000-99 999 tkr',
            'legalEntityText': 'Aktiebolag',
            'legalEntity': 'AB',
            'numberOfUnits': 1,
            'netSales': 78900.0,
            'operatingResult': 9100.0,
            'netProfitLoss': 7050.0,
            'growthPct': 9.1,
            'headcountChangePct': 4.0,
            'solidityPct': 61.0,
            'operatingMarginPct': 11.5,
            'profitMarginPct': 8.9,
            'quickRatioPct': 188.0,
            'cashAtBank': 21400.0,
            'totalAssets': 54300.0,
            'totalEquity': 33100.0,
            'accountDateTo': '2025-12-31',
            'accountMonths': 12,
            'accountantObligation': True,
            'directorName': 'Erik Lund',
            'directorRole': 'Styrelseordförande',
            'registrationDate': '2005-09-01',
            'companyFormedDate': '2005-08-10',
            'statusDate': '2018-06-30',
        },
        {
            'name': 'Innovativa Lösningar i Norr AB',
            'organisationNumber': '5599887766',
            'vatNumber': 'SE559988776601',
            'phone': '+46 90 55 66 77',
            'fax': '',
            'address': 'Kungsgatan 50',
            'postCode': '90325',
            'city': 'Umeå',
            'postCommunity': 'Umeå',
            'visitingAddress': 'Kungsgatan 50',
            'visitingPostCode': '90325',
            'visitingCity': 'Umeå',
            'visitingCommunity': 'Umeå',
            'description': '70220 Konsultverksamhet avseende företags org.',
            'employees': '5-9 anställda',
            'turnOver': '1 000-9 999 tkr',
            'legalEntityText': 'Aktiebolag',
            'legalEntity': 'AB',
            'numberOfUnits': 1,
            'netSales': 8650.0,
            'operatingResult': 540.0,
            'netProfitLoss': 410.0,
            'growthPct': 33.7,
            'headcountChangePct': 25.0,
            'solidityPct': 38.5,
            'operatingMarginPct': 6.2,
            'profitMarginPct': 4.7,
            'quickRatioPct': 104.0,
            'cashAtBank': 1200.0,
            'totalAssets': 4900.0,
            'totalEquity': 1890.0,
            'accountDateTo': '2025-12-31',
            'accountMonths': 12,
            'accountantObligation': False,
            'directorName': 'Sara Berg',
            'directorRole': 'VD',
            'registrationDate': '2019-11-22',
            'companyFormedDate': '2019-10-01',
            'statusDate': '2019-11-22',
        },
    ]

    # Sample REVEAL dicts -- one per company, keyed by the SAME organisation
    # numbers as the search rows above so a full search -> select -> create
    # flow resolves end to end (``action_create_leads`` builds
    # ``{r['organisationNumber']: r for r in client.reveal(...)}`` then looks
    # each selected line up by its organisation number). The first entry carries
    # the full superset of keys ``_format_notes`` renders; the others cover the
    # fields ``action_create_leads`` writes onto the crm.lead.
    REVEAL_ROWS = [
        {
            'name': 'Nordfält Bygg AB',
            'organisationNumber': '5566778899',
            'vatNumber': 'SE556677889901',
            'description': '41200 Byggande av bostadshus och andra byggnader',
            'legalEntityText': 'Aktiebolag',
            'legalEntity': 'AB',
            'postCommunity': 'Stockholm',
            'companyFormedDate': '2011-02-01',
            'registrationDate': '2011-03-14',
            'statusDate': '2011-03-14',
            'numberOfUnits': 2,
            'directorName': 'Anna Nordfält',
            'directorRole': 'VD',
            'phone': '+46 8 123 45 67',
            'fax': '+46 8 123 45 68',
            'address': 'Storgatan 1',
            'postCode': '11122',
            'city': 'Stockholm',
            'visitingAddress': 'Storgatan 1',
            'visitingPostCode': '11122',
            'visitingCity': 'Stockholm',
            'visitingCommunity': 'Stockholm',
            'registeredAddress': 'Box 1234',
            'registeredPostCode': '11185',
            'registeredCity': 'Stockholm',
            'employees': '10-19 anställda',
            'turnOver': '10 000-49 999 tkr',
            'accountDateTo': '2025-12-31',
            'accountMonths': 12,
            'netSales': 42150.0,
            'netOperatingIncome': 42600.0,
            'operatingResult': 3120.0,
            'profitLossAfterFin': 2980.0,
            'netProfitLoss': 2480.0,
            'growthPct': 18.4,
            'headcountChangePct': 12.5,
            'solidityPct': 47.2,
            'operatingMarginPct': 7.4,
            'profitMarginPct': 5.9,
            'quickRatioPct': 132.0,
            'turnoverPerEmployee': 2810.0,
            'cashAtBank': 5600.0,
            'totalAssets': 28800.0,
            'totalEquity': 13600.0,
            'currentLiabilities': 9200.0,
            'longTermDebts': 6000.0,
            'dividend': 800.0,
            'accountantObligation': True,
        },
        {
            'name': 'Tjänstebolaget Väst AB',
            'organisationNumber': '5560123456',
            'vatNumber': 'SE556012345601',
            'description': '62010 Dataprogrammering',
            'legalEntityText': 'Aktiebolag',
            'legalEntity': 'AB',
            'postCommunity': 'Göteborg',
            'companyFormedDate': '2005-08-10',
            'registrationDate': '2005-09-01',
            'statusDate': '2018-06-30',
            'numberOfUnits': 1,
            'directorName': 'Erik Lund',
            'directorRole': 'Styrelseordförande',
            'phone': '+46 31 222 33 44',
            'address': 'Avenyn 12',
            'postCode': '41136',
            'city': 'Göteborg',
            'visitingAddress': 'Avenyn 12',
            'visitingPostCode': '41136',
            'visitingCity': 'Göteborg',
            'visitingCommunity': 'Göteborg',
            'registeredAddress': 'Avenyn 12',
            'registeredCity': 'Göteborg',
            'employees': '20-49 anställda',
            'turnOver': '50 000-99 999 tkr',
            'accountDateTo': '2025-12-31',
            'netSales': 78900.0,
            'operatingResult': 9100.0,
            'netProfitLoss': 7050.0,
            'growthPct': 9.1,
            'solidityPct': 61.0,
            'accountantObligation': True,
        },
        {
            'name': 'Innovativa Lösningar i Norr AB',
            'organisationNumber': '5599887766',
            'vatNumber': 'SE559988776601',
            'description': '70220 Konsultverksamhet avseende företags org.',
            'legalEntityText': 'Aktiebolag',
            'legalEntity': 'AB',
            'postCommunity': 'Umeå',
            'directorName': 'Sara Berg',
            'directorRole': 'VD',
            'phone': '+46 90 55 66 77',
            'address': 'Kungsgatan 50',
            'postCode': '90325',
            'city': 'Umeå',
            'visitingAddress': 'Kungsgatan 50',
            'visitingPostCode': '90325',
            'visitingCity': 'Umeå',
            'visitingCommunity': 'Umeå',
            'employees': '5-9 anställda',
            'turnOver': '1 000-9 999 tkr',
            'accountDateTo': '2025-12-31',
            'numberOfUnits': 1,
            'netSales': 8650.0,
            'operatingResult': 540.0,
            'netProfitLoss': 410.0,
            'growthPct': 33.7,
            'solidityPct': 38.5,
            'accountantObligation': False,
        },
    ]

    # Sample COMPANY-STATUS rows -- camelCase keys exactly as the
    # /api/v1/insight/company-status endpoint returns them and as
    # ``res.partner._bizfinder_status_vals`` reads them. Same org numbers as
    # SEARCH_ROWS so partner fixtures can share them.
    COMPANY_STATUS_ROWS = [
        {
            'orgNumber': '5566778899',
            'name': 'Nordfält Bygg AB',
            'statusCode': 100,
            'statusText': 'Aktivt',
            'fTax': True,
            'moms': True,
            'sniCode': '41200',
            'sniText': 'Byggande av bostadshus och andra byggnader',
            'legalEntity': 'AB',
            'legalEntityText': 'Aktiebolag',
            'employees': '10-19 anställda',
            'city': 'Stockholm',
            'regionName': 'Stockholms län',
            'communityName': 'Stockholm',
            'registrationDate': '2011-03-14',
            'netSales': 42150.0,
            'solidityPct': 47.2,
            'growthPct': 18.4,
            'profitMarginPct': 5.9,
            'quickRatioPct': 132.0,
            'operatingMarginPct': 7.4,
            'accountDateTo': '2025-12-31',
            'accountMonths': 12,
        },
        {
            'orgNumber': '5560123456',
            'name': 'Tjänstebolaget Väst AB',
            'statusCode': 100,
            'statusText': 'Aktivt',
            'fTax': True,
            'moms': True,
            'sniCode': '62010',
            'sniText': 'Dataprogrammering',
            'legalEntity': 'AB',
            'legalEntityText': 'Aktiebolag',
            'employees': '20-49 anställda',
            'city': 'Göteborg',
            'regionName': 'Västra Götalands län',
            'communityName': 'Göteborg',
            'registrationDate': '2005-09-01',
            'netSales': 78900.0,
            'solidityPct': 61.0,
            'growthPct': 9.1,
            'profitMarginPct': 8.9,
            'quickRatioPct': 188.0,
            'operatingMarginPct': 11.5,
            'accountDateTo': '2025-12-31',
            'accountMonths': 12,
        },
    ]

    # Sample EVENTS rows -- /api/v1/insight/events shape, detectedAt asc.
    EVENT_ROWS = [
        {
            'orgNumber': '5566778899',
            'companyName': 'Nordfält Bygg AB',
            'eventType': 'ADDRESS_CHANGED',
            'oldValue': 'Storgatan 1',
            'newValue': 'Nygatan 2',
            'detectedAt': '2025-08-01T08:00:00Z',
        },
        {
            'orgNumber': '5566778899',
            'companyName': 'Nordfält Bygg AB',
            'eventType': 'F_TAX_LOST',
            'oldValue': 'true',
            'newValue': 'false',
            'detectedAt': '2025-08-02T09:30:00Z',
        },
    ]

    # Sample LOOKUP rows -- /api/v1/insight/lookup shape (redacted tier: no
    # street/phone by contract).
    LOOKUP_ROWS = [
        {
            'name': 'Nordfält Bygg AB',
            'organisationNumber': '5566778899',
            'city': 'Stockholm',
            'legalEntityText': 'Aktiebolag',
            'sniText': 'Byggande av bostadshus och andra byggnader',
            'employees': '10-19 anställda',
        },
        {
            'name': 'Nordfält Fastigheter AB',
            'organisationNumber': '5566001122',
            'city': 'Uppsala',
            'legalEntityText': 'Aktiebolag',
            'sniText': 'Förvaltning av egna fastigheter',
            'employees': '1-4 anställda',
        },
    ]

    # Billing pricing payload, shape matching get_billing_pricing()
    # (keys: pricePerReveal, currency).
    PRICING = {'pricePerReveal': 9.5, 'currency': 'SEK'}

    # Billing usage payload, shape matching get_billing_usage()
    # (keys: clientId, currency, reveals, amount). Drives the manager-only
    # "This month" toolbar stat.
    USAGE = {'clientId': 'ACME-TEST', 'currency': 'SEK', 'reveals': 12, 'amount': 114.0}

    # Convenience: the org numbers shared by the search and reveal fixtures, in
    # the same order as SEARCH_ROWS.
    ORG_NUMBERS = [row['organisationNumber'] for row in SEARCH_ROWS]

    # Default total "hit count" returned by preview(). Equals the number of
    # sample rows so the happy path gives hit_count == returned_count; override
    # via ``mock_client(preview=...)`` to exercise the dedup / no-results paths.
    DEFAULT_HIT_COUNT = len(SEARCH_ROWS)

    # --------------------------------------------------------------- setup
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Loaded from data/bizfinder_source_data.xml at install; every lead the
        # wizard creates is tagged with this Source, and crm.lead.is_bizfinder_lead
        # keys its Bizfinder tab off it.
        cls.utm_source_bizfinder = cls.env.ref('bizfinder.utm_source_bizfinder')

    # --------------------------------------------------------- fixture access
    @classmethod
    def sample_search_rows(cls):
        """Deep copy of SEARCH_ROWS so a test can mutate rows without leaking
        into sibling tests."""
        return copy.deepcopy(cls.SEARCH_ROWS)

    @classmethod
    def sample_reveal_rows(cls):
        """Deep copy of REVEAL_ROWS (see :meth:`sample_search_rows`)."""
        return copy.deepcopy(cls.REVEAL_ROWS)

    @classmethod
    def sample_company_status_rows(cls):
        """Deep copy of COMPANY_STATUS_ROWS (see :meth:`sample_search_rows`)."""
        return copy.deepcopy(cls.COMPANY_STATUS_ROWS)

    @classmethod
    def sample_event_rows(cls):
        """Deep copy of EVENT_ROWS (see :meth:`sample_search_rows`)."""
        return copy.deepcopy(cls.EVENT_ROWS)

    @classmethod
    def sample_lookup_rows(cls):
        """Deep copy of LOOKUP_ROWS (see :meth:`sample_search_rows`)."""
        return copy.deepcopy(cls.LOOKUP_ROWS)

    @classmethod
    def sample_pricing(cls):
        """Fresh copy of the pricing payload."""
        return dict(cls.PRICING)

    @classmethod
    def sample_usage(cls):
        """Fresh copy of the billing-usage payload."""
        return dict(cls.USAGE)

    # ------------------------------------------------------------- builders
    def _new_wizard(self, **vals):
        """Build a usable ``bizfinder.search`` wizard record.

        Mirrors how the action opens it (``create({})``); pass field overrides
        as keyword arguments. Range / date envelope defaults come from
        ``bizfinder.filter.mixin`` so ``_build_values()`` works out of the box.
        """
        return self.env['bizfinder.search'].create(dict(vals))

    def _selected_lines(self, wizard):
        """The result lines currently flagged ``selected`` on a wizard."""
        return wizard.result_line_ids.filtered(lambda line: line.selected)

    # ------------------------------------------------------------- mocking
    @contextmanager
    def mock_client(self, search=_UNSET, preview=_UNSET, reveal=_UNSET,
                    pricing=_UNSET, usage=_UNSET, company_status=_UNSET,
                    events=_UNSET, lookup=_UNSET):
        """Patch every external ``BizfinderClient`` method the module calls.

        All eight are always patched so a test can never reach the network.
        Each argument may be a literal return value or a
        ``callable(client_recordset, *args, **kwargs)``; omitted arguments fall
        back to the shared sample fixtures.

        Usage::

            with self.mock_client():
                wizard.action_search()

            with self.mock_client(preview=4213, search=[]):
                wizard.action_search()  # exercises the "no results" branch
        """
        if search is _UNSET:
            search = self.sample_search_rows()
        if preview is _UNSET:
            preview = self.DEFAULT_HIT_COUNT
        if reveal is _UNSET:
            reveal = self.sample_reveal_rows()
        if pricing is _UNSET:
            pricing = self.sample_pricing()
        if usage is _UNSET:
            usage = self.sample_usage()
        if company_status is _UNSET:
            company_status = self.sample_company_status_rows()
        if events is _UNSET:
            events = self.sample_event_rows()
        if lookup is _UNSET:
            lookup = self.sample_lookup_rows()

        def _stub(value):
            # Plain function bound as the model method; ``_model`` is the
            # bizfinder.client recordset, remaining args are the call args
            # (e.g. values / skip / take / org_numbers).
            def _call(_model, *args, **kwargs):
                if callable(value):
                    return value(_model, *args, **kwargs)
                return value
            return _call

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(BizfinderClient, 'search', _stub(search)))
            stack.enter_context(
                patch.object(BizfinderClient, 'preview', _stub(preview)))
            stack.enter_context(
                patch.object(BizfinderClient, 'reveal', _stub(reveal)))
            stack.enter_context(
                patch.object(BizfinderClient, 'get_billing_pricing',
                             _stub(pricing)))
            stack.enter_context(
                patch.object(BizfinderClient, 'get_billing_usage',
                             _stub(usage)))
            stack.enter_context(
                patch.object(BizfinderClient, 'company_status',
                             _stub(company_status)))
            stack.enter_context(
                patch.object(BizfinderClient, 'events', _stub(events)))
            stack.enter_context(
                patch.object(BizfinderClient, 'lookup', _stub(lookup)))
            yield

    # ------------------------------------------------------ flow shortcuts
    def _run_search(self, wizard=None, **mock_kwargs):
        """Create (if needed) and search a wizard under a mocked client.

        Result lines are real DB records and persist after the mock context
        exits, so the returned wizard is ready to assert against.
        """
        wizard = wizard or self._new_wizard()
        with self.mock_client(**mock_kwargs):
            wizard.action_search()
        return wizard

    def _create_leads(self, wizard, billing_confirmed=True, **mock_kwargs):
        """Run ``action_create_leads`` under a mocked client.

        With ``billing_confirmed=True`` (the default) the billing-confirmation
        dialog is skipped via the ``bizfinder_billing_confirmed`` context key,
        so the leads are created directly and the returned action targets them.
        """
        with self.mock_client(**mock_kwargs):
            wiz = wizard.with_context(bizfinder_billing_confirmed=billing_confirmed)
            return wiz.action_create_leads()
