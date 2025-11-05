
/** @odoo-module **/
import { CalendarCommonRenderer } from "@web/views/calendar/calendar_common/calendar_common_renderer";
import { patch } from "@web/core/utils/patch";
//import { deserializeDateTime } from "@web/core/l10n/dates";

// Properly save and call the original method in Odoo 17
const originalOnDateClick = CalendarCommonRenderer.prototype.onDateClick;

patch(CalendarCommonRenderer.prototype, {
    onDateClick(info) {
        if (info?.jsEvent?.defaultPrevented) {
            return;
        }

        // Only redirect month view to day view for CRM Lead calendar
        if (this.props.model.scale === "month" && this.props.model.resModel === "field.visit") {
            const clickedDate = luxon.DateTime.fromJSDate(info.date);
            console.log("Clicked", clickedDate)
            this.props.model.load({ date: clickedDate, scale: "day" });
        } else {
            // Call the original method using the saved reference
            originalOnDateClick.call(this, info);
        }
    }
});