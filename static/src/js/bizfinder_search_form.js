/** @odoo-module */

// Custom form view for the Bizfinder search wizard. Its only job is to
// reparent the form <header> (.o_form_statusbar) into the control-panel
// breadcrumb so the user sees a single header row instead of a stacked
// breadcrumb row + action button row. Selecting result rows is handled
// natively by the "Select all" / "Clear selection" header buttons, which
// write the records in a single ORM call.

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
        onMounted(moveStatusbarIntoBreadcrumb);
        onPatched(moveStatusbarIntoBreadcrumb);
    }
}

registry.category("views").add("bizfinder_search_form", {
    ...formView,
    Controller: BizfinderSearchFormController,
});
