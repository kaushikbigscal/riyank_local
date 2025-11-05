/** @odoo-module **/

import { registry } from "@web/core/registry";

async function getBrowserLocationAction(env, action) {
    const partnerId = action.context.active_id;

    // Check if browser supports geolocation
    if (!navigator.geolocation) {
        env.services.notification.add(
            "Geolocation is not supported by this browser",
            { type: "warning" }
        );
        return;
    }

    env.services.notification.add(
        "Requesting your location...",
        { type: "info" }
    );

    return new Promise((resolve) => {
        navigator.geolocation.getCurrentPosition(
            async (position) => {
                try {
                    await env.services.orm.call(
                        'res.partner',
                        'set_browser_location',
                        [partnerId, position.coords.latitude, position.coords.longitude]
                    );

                    env.services.notification.add(
                        `Location saved!`,
                        { type: "success" }
                    );

                    // Reload the current view
                    await env.services.action.doAction({
                        type: 'ir.actions.act_window',
                        res_model: 'res.partner',
                        res_id: partnerId,
                        views: [[false, 'form']],
                        view_mode: 'form',
                        target: 'current',
                    });

                } catch (error) {
                    env.services.notification.add(
                        "Failed to save location: " + error.message,
                        { type: "danger" }
                    );
                }
                resolve();
            },
            (error) => {
                let errorMessage = "";
                switch(error.code) {
                    case error.PERMISSION_DENIED:
                        errorMessage = "You denied location access. Please enable it in browser settings.";
                        break;
                    case error.POSITION_UNAVAILABLE:
                        errorMessage = "Location information is unavailable.";
                        break;
                    case error.TIMEOUT:
                        errorMessage = "Location request timed out. Please try again.";
                        break;
                    default:
                        errorMessage = "An unknown error occurred.";
                        break;
                }

                env.services.notification.add(
                    errorMessage,
                    { type: "danger" }
                );

                resolve();
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    });
}

registry.category("actions").add("get_browser_location", getBrowserLocationAction);




///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { Component } from "@odoo/owl";
//import { useService } from "@web/core/utils/hooks";
//
//export class BrowserLocationButton extends Component {
//    setup() {
//        console.log("🚀 BrowserLocationButton setup called");
//        this.orm = useService("orm");
//        this.notification = useService("notification");
//    }
//
//    async onGetBrowserLocation() {
//        console.log("=" .repeat(80));
//        console.log("📱 GET BROWSER LOCATION BUTTON CLICKED");
//        console.log("=" .repeat(80));
//
//        const partnerId = this.props.record.resId;
//        console.log("📋 Partner ID:", partnerId);
//
//        // Check if browser supports geolocation
//        if (!navigator.geolocation) {
//            console.error("❌ Geolocation not supported");
//            this.notification.add(
//                "Geolocation is not supported by this browser",
//                { type: "warning" }
//            );
//            return;
//        }
//
//        console.log("🔍 Requesting browser location...");
//        this.notification.add(
//            "Requesting your location...",
//            { type: "info" }
//        );
//
//        navigator.geolocation.getCurrentPosition(
//            async (position) => {
//                console.log("📍 Browser location received:");
//                console.log("   - Latitude:", position.coords.latitude);
//                console.log("   - Longitude:", position.coords.longitude);
//                console.log("   - Accuracy:", position.coords.accuracy, "meters");
//
//                try {
//                    console.log("📡 Calling set_browser_location...");
//                    await this.orm.call(
//                        'res.partner',
//                        'set_browser_location',
//                        [partnerId, position.coords.latitude, position.coords.longitude]
//                    );
//                    console.log("✅ ORM call completed");
//
//                    // Reload the record to show updated values
//                    await this.props.record.load();
//                    console.log("✅ Record reloaded");
//
//                    this.notification.add(
//                        `Location saved! (Accuracy: ${Math.round(position.coords.accuracy)}m)`,
//                        { type: "success" }
//                    );
//                    console.log("✅ Success notification shown");
//                } catch (error) {
//                    console.error("❌ Error saving location:", error);
//                    this.notification.add(
//                        "Failed to save location: " + error.message,
//                        { type: "danger" }
//                    );
//                }
//            },
//            (error) => {
//                console.error("❌ Browser geolocation error:");
//                console.error("   - Code:", error.code);
//                console.error("   - Message:", error.message);
//
//                let errorMessage = "";
//                switch(error.code) {
//                    case error.PERMISSION_DENIED:
//                        errorMessage = "You denied location access. Please enable it in browser settings.";
//                        break;
//                    case error.POSITION_UNAVAILABLE:
//                        errorMessage = "Location information is unavailable.";
//                        break;
//                    case error.TIMEOUT:
//                        errorMessage = "Location request timed out. Please try again.";
//                        break;
//                    default:
//                        errorMessage = "An unknown error occurred.";
//                        break;
//                }
//                console.error("   - Error type:", errorMessage);
//
//                this.notification.add(
//                    errorMessage,
//                    { type: "danger" }
//                );
//            },
//            {
//                enableHighAccuracy: true,
//                timeout: 10000,
//                maximumAge: 0
//            }
//        );
//
//        console.log("=" .repeat(80));
//    }
//}
//
//BrowserLocationButton.template = "partner_location_picker.BrowserLocationButton";
//
//console.log("✅ BrowserLocationButton component defined");
//
//export const browserLocationButton = {
//    component: BrowserLocationButton,
//};
//
//console.log("✅ Registering browser_location_button widget");
//registry.category("view_widgets").add("browser_location_button", browserLocationButton);
//console.log("✅ Widget registered successfully");



///** @odoo-module **/
//
//import { registry } from "@web/core/registry";
//import { Component } from "@odoo/owl";
//import { useService } from "@web/core/utils/hooks";
//
//export class BrowserLocationButton extends Component {
//    setup() {
//        console.log("🚀 BrowserLocationButton setup called");
//        this.orm = useService("orm");
//        this.notification = useService("notification");
//    }
//
//    async onGetBrowserLocation() {
//        console.log("=".repeat(80));
//        console.log("📱 GET BROWSER LOCATION BUTTON CLICKED");
//        console.log("=".repeat(80));
//
//        const partnerId = this.props.record.resId;
//        console.log("📋 Partner ID:", partnerId);
//
//        if (!navigator.geolocation) {
//            console.error("❌ Geolocation not supported");
//            this.notification.add(
//                "Geolocation is not supported by this browser",
//                { type: "warning" }
//            );
//            return;
//        }
//
//        console.log("🔍 Requesting browser location...");
//        this.notification.add(
//            "Requesting your location...",
//            { type: "info" }
//        );
//
//        navigator.geolocation.getCurrentPosition(
//            async (position) => {
//                console.log("📍 Browser location received:");
//                console.log("   - Latitude:", position.coords.latitude);
//                console.log("   - Longitude:", position.coords.longitude);
//                console.log("   - Accuracy:", position.coords.accuracy, "meters");
//
//                // --- Reverse Geocoding using Nominatim ---
//                try {
//                    const lat = position.coords.latitude;
//                    const lon = position.coords.longitude;
//                    const response = await fetch(`https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`);
//                    const data = await response.json();
//
//                    if (data && data.display_name) {
//                        console.log("🏠 Address from coordinates:", data.display_name);
//                        this.notification.add(
//                            `Address found: ${data.display_name}`,
//                            { type: "info" }
//                        );
//                    } else {
//                        console.warn("⚠️ No address found for these coordinates");
//                    }
//                } catch (error) {
//                    console.error("❌ Reverse geocoding failed:", error);
//                }
//
//                // --- Save location via ORM ---
//                try {
//                    console.log("📡 Calling set_browser_location...");
//                    await this.orm.call(
//                        'res.partner',
//                        'set_browser_location',
//                        [partnerId, position.coords.latitude, position.coords.longitude]
//                    );
//                    console.log("✅ ORM call completed");
//
//                    await this.props.record.load();
//                    console.log("✅ Record reloaded");
//
//                    this.notification.add(
//                        `Location saved! (Accuracy: ${Math.round(position.coords.accuracy)}m)`,
//                        { type: "success" }
//                    );
//                    console.log("✅ Success notification shown");
//                } catch (error) {
//                    console.error("❌ Error saving location:", error);
//                    this.notification.add(
//                        "Failed to save location: " + error.message,
//                        { type: "danger" }
//                    );
//                }
//            },
//            (error) => {
//                console.error("❌ Browser geolocation error:");
//                console.error("   - Code:", error.code);
//                console.error("   - Message:", error.message);
//
//                let errorMessage = "";
//                switch(error.code) {
//                    case error.PERMISSION_DENIED:
//                        errorMessage = "You denied location access. Please enable it in browser settings.";
//                        break;
//                    case error.POSITION_UNAVAILABLE:
//                        errorMessage = "Location information is unavailable.";
//                        break;
//                    case error.TIMEOUT:
//                        errorMessage = "Location request timed out. Please try again.";
//                        break;
//                    default:
//                        errorMessage = "An unknown error occurred.";
//                        break;
//                }
//                console.error("   - Error type:", errorMessage);
//
//                this.notification.add(
//                    errorMessage,
//                    { type: "danger" }
//                );
//            },
//            {
//                enableHighAccuracy: true,
//                timeout: 10000,
//                maximumAge: 0
//            }
//        );
//
//        console.log("=".repeat(80));
//    }
//}
//
//BrowserLocationButton.template = "partner_location_picker.BrowserLocationButton";
//
//console.log("✅ BrowserLocationButton component defined");
//
//export const browserLocationButton = {
//    component: BrowserLocationButton,
//};
//
//console.log("✅ Registering browser_location_button widget");
//registry.category("view_widgets").add("browser_location_button", browserLocationButton);
//console.log("✅ Widget registered successfully");
//
//
//


