/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";

console.log("📦 GPS patch for ActivityMenu loaded (auto GPS without confirm)");

patch(ActivityMenu.prototype, {
    async signInOut() {
        const gpsTracker = window.odoo?.gpsTracker;
        const wasCheckedIn = this.state.checkedIn;

        console.log("📍 Patched signInOut triggered. Was checked in?", wasCheckedIn);
////////////////////////////////////////////////////////////////////////////////////////////

        // Check if GPS tracking is enabled for current user before proceeding
        let isGpsEnabled = false;
        if (gpsTracker) {
            isGpsEnabled = await gpsTracker.isGpsTrackingEnabled();
            console.log("GPS tracking enabled for user:", isGpsEnabled);
        }
//////////////////////////////////////////////////////////////////////////////////////////

        navigator.geolocation.getCurrentPosition(
            async ({ coords: { latitude, longitude } }) => {
                // Send attendance with location
                await this.rpc("/web/hr_attendance/systray_check_in_out", {
                    latitude,
                    longitude,
                });

                await this.searchReadEmployee();
//////////////////////////////////////////////////////////////////////////////////////////

                // Start or stop GPS tracking only if enabled
                if (gpsTracker && isGpsEnabled) {
                    if (!wasCheckedIn) {
                        console.log("Starting GPS tracking (user has permission)");
                        const started = await gpsTracker.startGPSTracking();
                        if (!started) {
                            console.log("GPS tracking failed to start");
                        }
                    } else {
                        console.log("Stopping GPS tracking");
                        await gpsTracker.stopGPSTracking();
                    }
                } else if (gpsTracker && !isGpsEnabled) {
                    console.log("GPS tracking is disabled for this user - skipping GPS operations");
                } else {
                    console.log("GPS tracker not available");
                }
            },
//////////////////////////////////////////////////////////////////////////////////////////

            async (error) => {
                console.warn("⚠️ Geolocation error:", error.message);
                alert("GPS access denied or failed. Attendance is still recorded.");

                await this.rpc("/web/hr_attendance/systray_check_in_out");
                await this.searchReadEmployee();

//////////////////////////////////////////////////////////////////////////////////////

                // Still stop GPS if user was checked in and GPS is enabled
                if (gpsTracker && wasCheckedIn && isGpsEnabled) {
                    console.log("Stopping GPS tracking (after geolocation error)");
                    await gpsTracker.stopGPSTracking();
                }

//////////////////////////////////////////////////////////////////////////////////////
            },
            {
                enableHighAccuracy: true,
                timeout: 8000,
                maximumAge: 0,
            }
        );
    }
});
