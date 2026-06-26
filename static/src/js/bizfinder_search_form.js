/** @odoo-module */

// Custom form view for the Bizfinder search wizard. It does two things on
// top of the standard form view:
//   1. Reparents the form <header> (.o_form_statusbar) into the control-panel
//      breadcrumb so the user sees a single header row.
//   2. Adds a "select all" checkbox to the results list header. The toggle
//      drives the records through the form model (not by clicking each row's
//      DOM checkbox), so it reliably (de)selects EVERY result — including
//      rows on other list pages and rows not currently in edit mode, which
//      the old click-each-checkbox approach silently missed.

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched } from "@odoo/owl";

class BizfinderSearchFormController extends FormController {
    setup() {
        super.setup();

        // The StaticList backing result_line_ids, or null before it loads.
        const resultList = () => this.model?.root?.data?.result_line_ids || null;

        const moveStatusbarIntoBreadcrumb = () => {
            const statusbar = document.querySelector(
                ".o_form_view.o_bizfinder_search_form .o_form_statusbar"
            );
            const breadcrumb = document.querySelector(
                ".o_control_panel .o_breadcrumb"
            );
            if (!statusbar || !breadcrumb) {
                return;
            }
            // Prepend so the action buttons sit to the LEFT of the
            // "Prospect" breadcrumb title rather than right of the pager.
            if (breadcrumb.firstChild !== statusbar) {
                breadcrumb.insertBefore(statusbar, breadcrumb.firstChild);
            }
        };

        const setAllSelected = async (checked) => {
            const list = resultList();
            if (!list) {
                return;
            }
            // Update every record in the model, regardless of which list page
            // is currently rendered. Sequential awaits keep the model writes
            // ordered and let the view re-render once at the end.
            for (const record of list.records) {
                if (record.data.selected !== checked) {
                    await record.update({ selected: checked });
                }
            }
        };

        const syncSelectAllCheckbox = () => {
            const form = document.querySelector(".o_form_view.o_bizfinder_search_form");
            const listEl = form?.querySelector("[name='result_line_ids']");
            if (!listEl) {
                return;
            }
            const selectedHeader = listEl.querySelector(
                "thead th[data-name='selected'], thead th[name='selected']"
            );
            if (!selectedHeader) {
                return;
            }
            let selectAll = selectedHeader.querySelector(".o_bizfinder_select_all");
            if (!selectAll) {
                selectAll = document.createElement("input");
                selectAll.type = "checkbox";
                selectAll.className = "form-check-input o_bizfinder_select_all";
                selectAll.title = "Select all";
                selectAll.setAttribute("aria-label", "Select all results");
                selectAll.addEventListener("click", (ev) => ev.stopPropagation());
                selectAll.addEventListener("change", () => setAllSelected(selectAll.checked));
                selectedHeader.textContent = "";
                selectedHeader.appendChild(selectAll);
            }

            // Reflect the model's selection state on the header checkbox.
            const records = resultList()?.records || [];
            const total = records.length;
            const checkedCount = records.filter((r) => r.data.selected).length;
            selectAll.checked = total > 0 && checkedCount === total;
            selectAll.indeterminate = checkedCount > 0 && checkedCount < total;
        };

        onMounted(moveStatusbarIntoBreadcrumb);
        onMounted(syncSelectAllCheckbox);
        onPatched(() => {
            moveStatusbarIntoBreadcrumb();
            syncSelectAllCheckbox();
        });
    }
}

registry.category("views").add("bizfinder_search_form", {
    ...formView,
    Controller: BizfinderSearchFormController,
});
