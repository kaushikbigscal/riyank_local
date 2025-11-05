/** @odoo-module **/

import { registry } from "@web/core/registry";

function CallPartnerAction(env, action) {
    let phone = action.params?.phone;
    if (phone) {
        phone = phone.toString().replace(/\s+/g, "");
        window.open(`tel:${phone}`, "_blank");
    } else {
        console.warn("No phone number provided.");
    }
    return Promise.resolve();
}

registry.category("actions").add("call_partner_action", CallPartnerAction);
 
