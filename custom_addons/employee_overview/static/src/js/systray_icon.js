/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component } from "@odoo/owl";

class SystrayIcon extends Component {
   setup() {
       super.setup(...arguments);
       this.action = useService("action");
   }

   _openApprovedLeaves() {
       // Use the xmlID of the action directly
       this.action.doAction("employee_overview.action_employee_leave_report");
   }
}

SystrayIcon.template = "systray_icon";
export const systrayItem = { Component: SystrayIcon };
registry.category("systray").add("SystrayIcon", systrayItem, { sequence: 50 });