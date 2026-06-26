/** @odoo-module */

// Custom form view for the Bizfinder search wizard. It does two things:
//   1. Reparents the form <header> (.o_form_statusbar) into the control-panel
//      breadcrumb so the Search button sits on the same row as the title.
//   2. Injects a cogwheel dropdown next to the "Bizfinder" breadcrumb title
//      that collects the preset-management actions (save / update / clear /
//      manage). Each item saves the record then calls the matching server
//      method and runs whatever action it returns.

import { registry } from "@web/core/registry";
import { formView } from "@web/views/form/form_view";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";
import { onMounted, onPatched } from "@odoo/owl";

const PRESET_ACTIONS = [
    { method: "action_save_preset", label: "Save as preset", icon: "fa-floppy-o" },
    { method: "action_update_preset", label: "Update preset", icon: "fa-refresh", needsPreset: true },
    { method: "action_clear_preset", label: "Clear preset", icon: "fa-eraser", needsPreset: true },
    { method: "action_manage_presets", label: "Manage presets", icon: "fa-cog" },
];

class BizfinderSearchFormController extends FormController {
    setup() {
        super.setup();
        this.actionService = useService("action");
        this.ormService = useService("orm");

        const runPresetAction = async (method) => {
            const root = this.model.root;
            await root.save();
            const result = await this.ormService.call("bizfinder.search", method, [[root.resId]]);
            if (result && typeof result === "object") {
                await this.actionService.doAction(result, { onClose: () => this.model.load() });
            } else {
                await this.model.load();
            }
        };

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

        // Close the preset dropdown when clicking anywhere else. Bound once.
        if (!this._bizfinderOutsideBound) {
            this._bizfinderOutsideBound = true;
            document.addEventListener("click", (ev) => {
                const menu = document.querySelector(".o_bizfinder_preset_menu");
                if (menu && !menu.contains(ev.target)) {
                    menu.classList.remove("show");
                    menu.querySelector(".dropdown-menu")?.classList.remove("show");
                }
            });
        }

        const renderPresetMenu = () => {
            const breadcrumb = document.querySelector(".o_control_panel .o_breadcrumb");
            if (!breadcrumb || !this.model.root) {
                return;
            }
            // Rebuild each patch so item visibility tracks the preset state.
            breadcrumb.querySelector(".o_bizfinder_preset_menu")?.remove();
            const hasPreset = Boolean(this.model.root.data.preset_id);

            const wrap = document.createElement("div");
            wrap.className = "dropdown o_bizfinder_preset_menu d-inline-block ms-2";

            const toggle = document.createElement("button");
            toggle.type = "button";
            toggle.className = "btn btn-secondary dropdown-toggle";
            toggle.title = "Presets";
            toggle.innerHTML = '<i class="fa fa-cog"></i>';
            toggle.addEventListener("click", (ev) => {
                ev.stopPropagation();
                wrap.classList.toggle("show");
                menu.classList.toggle("show");
            });

            const menu = document.createElement("ul");
            menu.className = "dropdown-menu";
            for (const action of PRESET_ACTIONS) {
                if (action.needsPreset && !hasPreset) {
                    continue;
                }
                const li = document.createElement("li");
                const item = document.createElement("a");
                item.className = "dropdown-item";
                item.href = "#";
                item.innerHTML = `<i class="fa ${action.icon} me-2"></i>${action.label}`;
                item.addEventListener("click", (ev) => {
                    ev.preventDefault();
                    ev.stopPropagation();
                    wrap.classList.remove("show");
                    menu.classList.remove("show");
                    runPresetAction(action.method);
                });
                li.appendChild(item);
                menu.appendChild(li);
            }

            wrap.appendChild(toggle);
            wrap.appendChild(menu);
            breadcrumb.appendChild(wrap);
        };

        onMounted(() => {
            moveStatusbarIntoBreadcrumb();
            renderPresetMenu();
        });
        onPatched(() => {
            moveStatusbarIntoBreadcrumb();
            renderPresetMenu();
        });
    }
}

registry.category("views").add("bizfinder_search_form", {
    ...formView,
    Controller: BizfinderSearchFormController,
});
