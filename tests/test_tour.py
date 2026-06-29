# -*- coding: utf-8 -*-

"""Browser tour over the bizfinder search wizard's custom frontend.

Drives the JS tour ``bizfinder_search_tour`` (static/tests/tours/
bizfinder_search_tour.js) against the live web client to guard the DOM surgery
in static/src/js/bizfinder_search_form.js:

* the form ``<header>`` (``.o_form_statusbar``) reparented into the control-panel
  breadcrumb (Search button + preset cog on the title row);
* the select-all ``<input>`` injected into the results list's Select column header
  (toggling it calls action_select_all / action_deselect_all then reloads);
* the preset cog Dropdown and its "Manage presets" item, which historically
  crashed the web client and must now open the Presets list cleanly.

The whole tour runs inside :meth:`BizfinderTestCommon.mock_client`, which
patches the four ``BizfinderClient`` methods process-wide. The in-process HTTP
test-server thread that handles the tour's RPCs (action_search ->
preview/search, billing pricing) therefore sees the patch and returns the
shared fixtures, so ``_creds()`` / ``_request()`` are never reached -- no token,
URL or network call is needed.
"""

from odoo.tests import HttpCase, tagged

from odoo.addons.bizfinder.tests.common import BizfinderTestCommon


@tagged('-at_install', 'post_install')
class TestBizfinderSearchTour(BizfinderTestCommon, HttpCase):
    """HttpCase + BizfinderTestCommon: reuse the fixtures/mock helper and the
    HTTP/browser machinery. Both ultimately derive from TransactionCase, so the
    cooperative ``setUpClass`` chain (BizfinderTestCommon -> HttpCase ->
    TransactionCase) initialises the source-data fixtures and the test server."""

    def test_bizfinder_search_tour(self):
        # start_tour blocks for the full duration of the tour, so the mock must
        # wrap the whole call. admin holds sales_team.group_sale_salesman, which
        # gates the Bizfinder menu and the bizfinder.search ACL.
        with self.mock_client():
            self.start_tour(
                '/odoo/bizfinder',
                'bizfinder_search_tour',
                login='admin',
                timeout=180,
            )
