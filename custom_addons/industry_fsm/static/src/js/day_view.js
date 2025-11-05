/** @odoo-module **/
import { CalendarModel } from "@web/views/calendar/calendar_model";
import { patch } from "@web/core/utils/patch";

// Patch the CalendarModel to set default scale to "day" for field.visit
patch(CalendarModel.prototype, {
    async load(params = {}) {
        // Force day scale for field.visit model, but allow dynamic view switching
        if (this.resModel === "project.task") {
            // If the scale isn't already set, default to 'day'
            if (!params.scale) {
                params = { ...params, scale: "day" };
            }
        }

        return super.load(params);
    }
});
