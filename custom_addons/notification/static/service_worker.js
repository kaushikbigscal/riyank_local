self.addEventListener('push', function(event) {
    console.log("📩 Push event received in SW:", event);
    const data = event.data ? event.data.json() : {};
    event.waitUntil(
        self.registration.showNotification(data.title, {
            body: data.body,
            icon: data.icon || '/web/image/res.company/1/logo',
            data: { url: data.url },
        })
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url || '/')
    );
});
