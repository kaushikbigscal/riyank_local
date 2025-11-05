/** @odoo-module **/

import { registry } from "@web/core/registry";
import { jsonrpc } from "@web/core/network/rpc_service";

function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");

    const rawData = atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }

    return outputArray;
}

export const portalNotificationService = {
    dependencies: ["bus_service", "notification"],

    async start(env, { bus_service, notification }) {

        let partnerId = null;
        try {
            const result = await jsonrpc("/notification/partner_id");
            partnerId = result.partner_id;
        } catch (err) {
            console.error("Error fetching partner_id:", err);
            return;
        }

        if (!partnerId) return;

        const channel = `portal_notification_${partnerId}`;
        bus_service.addChannel(channel);
        bus_service.addEventListener(channel, ({ detail }) => {
            const {
                message,
                title = "Notification",
                type = "info",
                task_id = null,
            } = detail;

            notification.add(message, { title, type, sticky: true });

            if (Notification.permission === "granted") {
                new Notification(title, {
                    body: message,
                    icon: "/web/image/res.company/1/logo",
                });
            }
        });

        await bus_service.start();

        // Fetch VAPID key from backend
        let vapidPublicKey = null;
        try {
            const response = await jsonrpc("/notification/get_vapid_key");
            vapidPublicKey = response.public_key;

        } catch (e) {
            console.error("Could not fetch VAPID key:", e);
            return;
        }

        if (!vapidPublicKey) {
            console.warn("No VAPID key provided from backend");
            return;
        }

        if ("serviceWorker" in navigator && "PushManager" in window) {
            try {
                const registration = await navigator.serviceWorker.register("/service_worker.js");

                const swReady = await navigator.serviceWorker.ready;

                if (Notification.permission !== "granted") {
                    const permission = await Notification.requestPermission();
                    if (permission !== "granted") {
                        console.warn("Notification permission denied.");
                        return;
                    }
                }

                // Always clean old subscriptions (to avoid stale key issues)
                const existingSub = await swReady.pushManager.getSubscription();
                if (existingSub) {
                    await existingSub.unsubscribe();
                }

                // Create new subscription using current VAPID key
                const newSubscription = await swReady.pushManager.subscribe({
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(vapidPublicKey),
                });

                await jsonrpc("/webpush/save_subscription", {
                    subscription: newSubscription.toJSON(),
                });


            } catch (err) {
                console.error("WebPush registration failed:", err);
            }
        } else {
            console.warn("Service Worker or PushManager not supported in this browser.");
        }
    },
};

registry.category("services").add("portal_notification", portalNotificationService);
