/** @odoo-module **/

import { DebugMenuBasic } from "@web/core/debug/debug_menu_basic";
import { patch } from "@web/core/utils/patch";
import { session } from "@web/session";
import { registry } from "@web/core/registry";
import { onWillStart } from "@odoo/owl";

console.log("TEST ASSET LOAD: DebugMenuBasic imported successfully!");

patch(DebugMenuBasic.prototype, {
    setup() {
        super.setup();
        this.user_debug = session.user_group[0];
    },

    onRestrictedDebugClick(ev) {
        ev.stopPropagation();
        ev.preventDefault();

        this.showFullScreenAccessDenied();
    },

    showFullScreenAccessDenied() {
        let countdown = 5;

        const overlay = document.createElement("div");
        overlay.id = "oe_full_screen_restrict_overlay";

        overlay.innerHTML = `
            <h1>ACCESS DENIED</h1>
            <p>You are not allowed to use Debug Mode.</p>
            <div class="countdown">Refreshing in <span id="oe_countdown_timer">${countdown}</span> seconds...</div>
        `;

        document.body.appendChild(overlay);

        const countdownElement = document.getElementById("oe_countdown_timer");

        const intervalId = setInterval(() => {
            countdown--;
            if (countdownElement) {
                countdownElement.textContent = countdown;
            }

            if (countdown <= 0) {
                clearInterval(intervalId);
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                window.location.reload();
            }
        }, 1000);
    },
});


registry.category("web.client_hooks").add("oe_restrict_debug_mode_ui_check", {
    setup() {
        onWillStart(() => {
            const isRestrictedForUI = session.user_group[0];

            if (isRestrictedForUI) {
                console.log("[DEBUG] Restrict UI: Initializing UI restrictions for", session.user_context.name, ".");

                const uiOverlay = document.createElement("div");
                uiOverlay.id = "oe_restrict_ui_overlay";
                uiOverlay.style.position = "fixed";
                uiOverlay.style.top = 0;
                uiOverlay.style.left = 0;
                uiOverlay.style.right = 0;
                uiOverlay.style.bottom = 0;
                uiOverlay.style.zIndex = "9998";
                uiOverlay.style.background = "rgba(0,0,0,0.01)";
                uiOverlay.style.pointerEvents = "none";
                document.body.appendChild(uiOverlay);

                document.addEventListener("contextmenu", e => {
                    e.preventDefault();
                    console.log("[DEBUG] Right-click prevented.");
                });

                document.addEventListener("keydown", e => {
                    if (e.key === "F12" || e.shiftKey || e.ctrlKey) {
                        e.preventDefault();
                        console.log(`[DEBUG] Key '${e.key}' prevented.`);
                    }
                });
            } else {
                const existingUiOverlay = document.getElementById("oe_restrict_ui_overlay");
                if (existingUiOverlay) {
                    existingUiOverlay.remove();
                }
            }
        });
    },
});