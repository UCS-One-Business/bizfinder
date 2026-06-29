/** @odoo-module */

// Backend tour over the bizfinder search wizard's custom frontend
// (static/src/js/bizfinder_search_form.js). It guards the fragile DOM surgery
// that has no other automated coverage:
//   1. the form <header> (.o_form_statusbar) reparented into the control-panel
//      breadcrumb, carrying the Search button + preset cog onto the title row;
//   2. the select-all <input> injected into the results list's Select column
//      header, and the action_select_all / action_deselect_all round-trip; and
//   3. the preset cog Dropdown -- both the Save-as-preset dialog and that
//      "Manage presets" now opens the preset list cleanly (the historical crash).
//
// The HttpCase that runs it patches bizfinder.client process-wide, so every RPC
// (action_search / get_billing_pricing / select / deselect / save / manage)
// returns canned SEARCH_ROWS fixtures and no network call is ever made.
//
// A /odoo/bizfinder backend tour loads the normal backend tour service after
// login, so -- unlike the sibling public-kiosk tour -- it needs no runner shim
// and no TourAutomatic import: just registry.add(...).

import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("bizfinder_search_tour", {
    steps: () => [
        // --- 1. Form loaded -------------------------------------------------
        {
            // The custom view (js_class="bizfinder_search_form") mounted.
            trigger: ".o_form_view.o_bizfinder_search_form",
        },
        // --- 2. Statusbar reparented into the breadcrumb --------------------
        {
            // moveStatusbarIntoBreadcrumb() prepended the form <header>
            // (.o_form_statusbar) into .o_control_panel .o_breadcrumb.
            trigger: ".o_control_panel .o_breadcrumb .o_form_statusbar",
        },
        {
            // ...and the Search button rode along inside it (proves the whole
            // header, not a clone, was moved).
            trigger:
                ".o_control_panel .o_breadcrumb .o_form_statusbar button[name='action_search']",
        },
        // --- 3. Run the (mocked) search ------------------------------------
        {
            // Click the reparented Search button; scoping under .o_control_panel
            // re-confirms it is no longer a descendant of the form sheet.
            trigger: ".o_control_panel button[name='action_search']",
            run: "click",
        },
        {
            // Mocked client.search returned SEARCH_ROWS -> rows render. Waiting
            // on a specific company name also lets the post-search onPatched run
            // (it injects / syncs the select-all checkbox).
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] .o_data_row:contains('Nordfält Bygg AB')",
        },
        // --- 4. Injected select-all checkbox: select, then deselect ---------
        {
            // Injection proof: the checkbox lives in the Select column header.
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] thead th[data-name='selected'] input.o_bizfinder_select_all",
        },
        {
            // Toggle it on -> action_select_all -> reload.
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] thead th[data-name='selected'] input.o_bizfinder_select_all",
            run: "click",
        },
        {
            // After the reload, syncSelectAllCheckbox sets checked = every row
            // selected (header state is computed from the model records).
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] thead input.o_bizfinder_select_all:checked",
        },
        {
            // A row's own Select cell is checked too (end-to-end selection).
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] .o_data_row td[name='selected'] input:checked",
        },
        {
            // Toggle it back off (clicks the now-checked box) -> action_deselect_all.
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] thead th[data-name='selected'] input.o_bizfinder_select_all:checked",
            run: "click",
        },
        {
            // Header checkbox reflects "nothing selected" again.
            trigger:
                ".o_bizfinder_search_form [name='result_line_ids'] thead input.o_bizfinder_select_all:not(:checked)",
        },
        // --- 5. Preset cog: Save-as-preset dialog opens & cancels -----------
        {
            // The cog button was reparented with the statusbar; open the menu.
            trigger: ".o_control_panel button[title='Presets']",
            run: "click",
        },
        {
            // The native Dropdown menu carries the custom menuClass.
            trigger: ".o_bizfinder_preset_cog_menu",
        },
        {
            // On a fresh wizard (no preset) only Save + Manage are listed.
            trigger:
                ".o_bizfinder_preset_cog_menu .dropdown-item:contains('Save current as preset')",
            run: "click",
        },
        {
            // action_save_preset returns the bizfinder.preset.save dialog; its
            // footer Save button proves the dialog mounted cleanly.
            trigger: ".modal button[name='action_save']",
        },
        {
            // Dismiss it without saving (onClose -> record.load()). Only the
            // cancel button carries the text "Cancel" inside the dialog.
            trigger: ".modal button:contains('Cancel')",
            run: "click",
        },
        {
            // Back on the search form with the cog available again.
            trigger: ".o_control_panel button[title='Presets']",
        },
        // --- 6. Manage presets opens the preset list cleanly (regression) ---
        {
            trigger: ".o_control_panel button[title='Presets']",
            run: "click",
        },
        {
            trigger:
                ".o_bizfinder_preset_cog_menu .dropdown-item:contains('Manage presets')",
            run: "click",
        },
        {
            // The historical crash was here: action_manage_presets now returns a
            // fully-resolved act_window, so the Presets list renders cleanly...
            trigger: ".o_list_view",
        },
        {
            // ...and the named action landed in the breadcrumb.
            trigger: ".o_breadcrumb:contains('Presets')",
        },
    ],
});
