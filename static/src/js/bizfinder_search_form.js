/** @odoo-module */

// Custom form view for the Bizfinder search wizard. The only thing
// it changes about the standard form view is that the form's
// <header> (rendered as .o_form_statusbar) is reparented into the
// control-panel breadcrumb so the user sees a single header row
// instead of a stacked breadcrumb row + action button row.

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched } from "@odoo/owl";

class BizfinderSearchFormController extends FormController {
    setup() {
        super.setup();
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
        const syncSelectAllCheckbox = () => {
            const form = document.querySelector(".o_form_view.o_bizfinder_search_form");
            const list = form?.querySelector("[name='result_line_ids']");
            if (!list) {
                return;
            }
            const selectedHeader = list.querySelector(
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
                selectAll.addEventListener("change", () => {
                    for (const checkbox of list.querySelectorAll(
                        "tbody td[data-name='selected'] input[type='checkbox'], tbody td[name='selected'] input[type='checkbox']"
                    )) {
                        if (checkbox.checked !== selectAll.checked) {
                            checkbox.click();
                        }
                    }
                });
                selectedHeader.textContent = "";
                selectedHeader.appendChild(selectAll);
            }

            if (!list.dataset.bizfinderSelectAllBound) {
                list.dataset.bizfinderSelectAllBound = "1";
                list.addEventListener("change", (ev) => {
                    if (ev.target.closest("tbody td[data-name='selected'], tbody td[name='selected']")) {
                        syncSelectAllCheckbox();
                    }
                });
            }

            const rowCheckboxes = [
                ...list.querySelectorAll(
                    "tbody td[data-name='selected'] input[type='checkbox'], tbody td[name='selected'] input[type='checkbox']"
                ),
            ];
            const checkedCount = rowCheckboxes.filter((checkbox) => checkbox.checked).length;
            selectAll.checked = rowCheckboxes.length > 0 && checkedCount === rowCheckboxes.length;
            selectAll.indeterminate = checkedCount > 0 && checkedCount < rowCheckboxes.length;
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
