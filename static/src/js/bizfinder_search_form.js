/** @odoo-module */

// Two pieces for the Bizfinder search wizard:
//   1. A "preset cog" view widget built on Odoo's native Dropdown component,
//      holding the preset-management actions (save / update / clear / manage).
//      Placed in the form <header> via <widget name="bizfinder_preset_cog"/>.
//   2. A thin form controller that reparents the form <header> (.o_form_statusbar)
//      into the control-panel breadcrumb, so the Search button and the cog sit
//      on the same row as the "Bizfinder" title.

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { standardWidgetProps } from "@web/views/widgets/standard_widget_props";
import { Dropdown } from "@web/core/dropdown/dropdown";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onPatched, xml } from "@odoo/owl";

class BizfinderPresetCog extends Component {
    static template = xml`
        <Dropdown items="menuItems" menuClass="'o_bizfinder_preset_cog_menu'">
            <button type="button" class="btn btn-secondary" title="Presets" aria-label="Presets">
                <i class="fa fa-cog"/>
            </button>
        </Dropdown>
    `;
    static components = { Dropdown };
    static props = { ...standardWidgetProps };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get menuItems() {
        const items = [
            { label: "Save current as preset", onSelected: () => this.run("action_save_preset") },
        ];
        if (this.props.record.data.preset_id) {
            items.push({ label: "Update current preset", onSelected: () => this.run("action_update_preset") });
            items.push({ label: "Clear preset", onSelected: () => this.run("action_clear_preset") });
        }
        items.push({ label: "Manage presets", onSelected: () => this.run("action_manage_presets") });
        return items;
    }

    async run(method) {
        const record = this.props.record;
        // Persist pending filter edits so the server method sees them, then
        // delegate to the matching wizard method and run any action it returns.
        await record.save();
        const result = await this.orm.call("bizfinder.search", method, [record.resId]);
        if (result && typeof result === "object") {
            await this.action.doAction(result, { onClose: () => record.load() });
        } else {
            await record.load();
        }
    }
}

registry.category("view_widgets").add("bizfinder_preset_cog", {
    component: BizfinderPresetCog,
});

class BizfinderSearchFormController extends FormController {
    setup() {
        super.setup();
        const moveStatusbarIntoBreadcrumb = () => {
            const statusbar = document.querySelector(
                ".o_form_view.o_bizfinder_search_form .o_form_statusbar"
            );
            const breadcrumb = document.querySelector(".o_control_panel .o_breadcrumb");
            if (!statusbar || !breadcrumb) {
                return;
            }
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
