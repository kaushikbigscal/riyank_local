/** @odoo-module **/

import { ActivityMenu as OriginalActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { registry } from "@web/core/registry";

function detectLoginType() {
    const userAgent = navigator.userAgent.toLowerCase();
    const mobileKeywords = ['mobile', 'android', 'iphone', 'ipad', 'tablet', 'blackberry', 'webos'];
    const isMobileUA = mobileKeywords.some(keyword => userAgent.includes(keyword));
    const isMobileScreen = window.matchMedia("(max-width: 1024px)").matches;
    const isTouchDevice = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    const isMobile = isMobileUA || (isMobileScreen && isTouchDevice);

    return isMobile ? 'mobile' : 'web';
}

function isMobileDevice() {
    return detectLoginType() === 'mobile';
}

function isIosApp() {
    return /iPad|iPhone|iPod/.test(navigator.userAgent) &&
           (window.webkit?.messageHandlers || window.ReactNativeWebView);
}

export class CustomAttendanceMenu extends OriginalActivityMenu {
    async searchReadEmployee() {
        // Call the parent method first to get the original data format
        await super.searchReadEmployee();

        // If we have employee data, add our custom logic
        if (this.employee && this.employee.id) {
            try {
                // Get the attendance capture mode from the user
                const userResult = await this.rpc("/web/dataset/call_kw", {
                    model: "res.users",
                    method: "read",
                    args: [[this.env.services.user.userId], ["attendance_capture_mode"]],
                    kwargs: {}
                });

                const mode = userResult[0]?.attendance_capture_mode || 'mobile-web';

                const isWeb = mode === "web" || mode === "mobile-web";
                const isMobile = mode === "mobile" || mode === "mobile-web";
                const isBiometric = mode === "biometric";

                const isMobileDeviceNow = isMobileDevice();
                const currentLoginType = detectLoginType();

                console.log(`Current device detection: ${currentLoginType}, isMobileDeviceNow: ${isMobileDeviceNow}`);
                console.log(`Attendance capture mode: ${mode}`);

                // Custom visibility logic based on attendance method + device
                if (isBiometric) {
                    this.state.isDisplayed = false;
                } else if (isWeb && !isMobileDeviceNow) {
                    this.state.isDisplayed = true;
                } else if (isMobile && isMobileDeviceNow) {
                    this.state.isDisplayed = true;
                } else {
                    this.state.isDisplayed = false;
                }
            } catch (error) {
                console.error("Error getting attendance capture mode:", error);
                // Fallback to default behavior
                this.state.isDisplayed = true;
            }
        }
    }

    async signInOut() {
        console.log("Hello from custom sign-in/out in custom module");
        console.log(`Device type detected: ${detectLoginType()}`);

        if (!isIosApp()) {
            navigator.geolocation.getCurrentPosition(
                async ({ coords: { latitude, longitude } }) => {
                    await this.rpc("/web/hr_attendance/systray_check_in_out", {
                        latitude,
                        longitude
                    });
                    await this.searchReadEmployee();
                },
                async () => {
                    await this.rpc("/web/hr_attendance/systray_check_in_out");
                    await this.searchReadEmployee();
                },
                { enableHighAccuracy: true }
            );
        } else {
            await this.rpc("/web/hr_attendance/systray_check_in_out");
            await this.searchReadEmployee();
        }
    }
}

// Override original systray component
registry.category("systray").add("hr_attendance.attendance_menu", {
    Component: CustomAttendanceMenu,
}, { force: true });


