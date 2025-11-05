/** @odoo-module **/
import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";


class NotificationSystray extends Component {
    setup() {
        super.setup();
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            isOpen: false,
            reminders: [],
            unreadCount: 0,
            activeTab: 'unread', // 'unread', 'read', or 'all'
            hoveredReminderId: null,  // Track which reminder is being hovered over
        });
        // Bind event handlers
        this.handleClickOutside = this.handleClickOutside.bind(this);
        this.handleKeyDown = this.handleKeyDown.bind(this);


        onMounted(() => {
            console.log("callinggggggggggggggg5555555555555555555555555555555555555555")
            this.fetchReminders();
            // Set up periodic refresh (every 1 minute)
            this.refreshInterval = setInterval(() => this.fetchReminders(), 60 * 1000);
        });

        onWillUnmount(() => {
            // Clean up event listeners and intervals
            this.removeEventListeners();
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
            }
        });
    }
        constructor() {
        super(...arguments);
        this.userTimezoneCache = null;
        this.fetchingTimezone = false; // Prevent parallel calls
    }

    /**
     * Add event listeners for click outside and ESC key
     */
    addEventListeners() {
        if (!this.clickOutsideListener) {
            document.addEventListener('click', this.handleClickOutside, true);
            this.clickOutsideListener = true;
        }
        if (!this.keyDownListener) {
            document.addEventListener('keydown', this.handleKeyDown, true);
            this.keyDownListener = true;
        }
    }

    /**
     * Remove event listeners
     */
    removeEventListeners() {
        if (this.clickOutsideListener) {
            document.removeEventListener('click', this.handleClickOutside, true);
            this.clickOutsideListener = false;
        }
        if (this.keyDownListener) {
            document.removeEventListener('keydown', this.handleKeyDown, true);
            this.keyDownListener = false;
        }
    }

    /**
     * Handle ESC key press to close dropdown
     */
    handleKeyDown(event) {
        console.log('Key pressed:', event.key, 'Dropdown open:', this.state.isOpen); // Debug log
        if ((event.key === 'Escape' || event.keyCode === 27) && this.state.isOpen) {
            event.preventDefault();
            event.stopPropagation();
            console.log('Closing dropdown with ESC key'); // Debug log
            this.closeDropdown();
        }
    }

    /**
     * Handle clicks outside the dropdown to close it
     */
    handleClickOutside(event) {
        if (!this.state.isOpen) return;

        const target = event.target;

        // Check if click is inside the notification systray component
        const systrayElement = target.closest('.o_notification_systray') ||
                               target.closest('[data-systray="NotificationSystray"]') ||
                               target.closest('.notification-systray');

        // If clicked outside the notification systray, close it
        if (!systrayElement) {
            this.closeDropdown();
            return;
        }

        // Additional checks for other systray items or main menu
        const isOtherSystrayClick = target.closest('.o_systray_item') && !systrayElement;
        const isMainMenuClick = target.closest('.o_menu_item') ||
                                target.closest('.o_menu_sections') ||
                                target.closest('.o_app') ||
                                target.closest('.dropdown-toggle') ||
                                target.closest('.o_menu_brand');

        if (isOtherSystrayClick || isMainMenuClick) {
            this.closeDropdown();
        }
    }

    /**
     * Close the dropdown and clean up event listeners
     */
    closeDropdown() {
        this.state.isOpen = false;
        this.removeEventListeners();
    }

    /**
     * Convert UTC datetime string to relative time (e.g., "2 days ago").
     */
    convertToRelativeTime(utcDatetimeStr) {
        if (!utcDatetimeStr) return "";
        const formatted = utcDatetimeStr.replace(" ", "T"); // Ensures valid format
        const utcDate = new Date(formatted + "Z"); // Force UTC
        const now = new Date();
        const diffMs = now - utcDate;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        const diffMonths = Math.floor(diffDays / 30);
        const diffYears = Math.floor(diffDays / 365);

        if (diffYears > 0) {
            return diffYears === 1 ? "1 year ago" : `${diffYears} years ago`;
        } else if (diffMonths > 0) {
            return diffMonths === 1 ? "1 month ago" : `${diffMonths} months ago`;
        } else if (diffDays > 0) {
            return diffDays === 1 ? "1 day ago" : `${diffDays} days ago`;
        } else {
            const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
            if (diffHours > 0) {
                return diffHours === 1 ? "1 hour ago" : `${diffHours} hours ago`;
            } else {
                const diffMinutes = Math.floor(diffMs / (1000 * 60));
                if (diffMinutes > 0) {
                    return diffMinutes === 1 ? "1 minute ago" : `${diffMinutes} minutes ago`;
                } else {
                    return "Just now";
                }
            }
        }
    }
     /**
     * Fetch user timezone from backend (alternative approach)
     */
    async getUserTimezoneFromBackend() {
        try {
            const result = await this.orm.call('res.users', 'read', [
                [this.env.services.user.userId],
                ['tz']
            ]);

            if (result && result[0] && result[0].tz) {
                return result[0].tz;
            }

            // Fallback to browser timezone
            return Intl.DateTimeFormat().resolvedOptions().timeZone;

        } catch (error) {
            console.error('Error fetching user timezone from backend:', error);
            return Intl.DateTimeFormat().resolvedOptions().timeZone;
        }
    }
    formatDateToLocal(dateObj) {
        if (!(dateObj instanceof Date) || isNaN(dateObj)) {
            return '';
        }
        try {
            const options = {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false,
            };
            return dateObj.toLocaleString('en-GB', options);  // Returns in DD/MM/YYYY, 24hr format
        } catch (err) {
            console.error("Error formatting local date:", err);
            return dateObj.toString();
        }
    }
    /**
     * Enhanced convertToLocalTime with backend timezone fetch
     */
    async convertToLocalTimeAsync(utcDatetimeStr) {
        if (!utcDatetimeStr) return "";

        try {
            // Get timezone from backend if not cached
            if (!this.userTimezoneCache) {
            this.userTimezoneCache = await this.getUserTimezone();
            }

            // Handle different datetime formats
            let isoString = utcDatetimeStr;
            if (utcDatetimeStr.includes(' ') && !utcDatetimeStr.includes('T')) {
                isoString = utcDatetimeStr.replace(' ', 'T');
            }
            if (!isoString.endsWith('Z') && !isoString.includes('+') && !isoString.includes('-', 10)) {
                isoString += 'Z';
            }

            const utcDate = new Date(isoString);
            if (isNaN(utcDate.getTime())) {
                return utcDatetimeStr;
            }

            // Convert using user's timezone
            if (this.userTimezoneCache && typeof Intl !== 'undefined') {
                try {
                    const formatter = new Intl.DateTimeFormat('en-GB', {
                        timeZone: this.userTimezoneCache,
                        year: 'numeric',
                        month: '2-digit',
                        day: '2-digit',
                        hour: '2-digit',
                        minute: '2-digit',
                        second: '2-digit',
                        hour12: false
                    });

                    const parts = formatter.formatToParts(utcDate);
                    const partsObj = parts.reduce((acc, part) => {
                        acc[part.type] = part.value;
                        return acc;
                    }, {});

                    return `${partsObj.day}-${partsObj.month}-${partsObj.year} ${partsObj.hour}:${partsObj.minute}:${partsObj.second}`;
                } catch (timezoneError) {
                    console.warn('Timezone conversion failed:', timezoneError);
                }
            }

            // Fallback to local formatting
            return this.formatDateToLocal(utcDate);

        } catch (error) {
            console.error('Error in async timezone conversion:', error);
            return utcDatetimeStr;
        }
    }
    async getUserTimezone() {
        if (this.userTimezoneCache) return this.userTimezoneCache;
        if (this.fetchingTimezone) return await this._waitForTimezone();

        this.fetchingTimezone = true;

        try {
            const userId = this.env.services.user.userId;
            const result = await this.orm.searchRead(
                'res.users',
                [['id', '=', userId]],
                ['tz']
            );
            const tz = result?.[0]?.tz || 'UTC';
            this.userTimezoneCache = tz;
            return tz;
        } catch (e) {
            console.error("Error in async timezone conversion:", e);
            return 'UTC';
        } finally {
            this.fetchingTimezone = false;
        }
    }
    _waitForTimezone() {
        return new Promise(resolve => {
            const interval = setInterval(() => {
                if (this.userTimezoneCache) {
                    clearInterval(interval);
                    resolve(this.userTimezoneCache);
                }
            }, 50);
        });
    }

    /**
     * Fetch reminders from the backend and populate the component state.
     */
    async fetchReminders() {
        try {
            // First check if AMC module is installed
            const isAMCModuleInstalled = await this.orm.call(
                'ir.module.module',
                'search_count',
                [[['name', '=', 'inventory_custom_tracking_installation_delivery'], ['state', '=', 'installed']]]
            );
            const reminders = await this.orm.call('task.reminder', 'get_user_reminders', []);

            // Filter out AMC reminders if module not installed
            const filteredReminders = isAMCModuleInstalled
                ? reminders
                : reminders.filter(r => r.related_model !== 'amc.contract');

            const newUnread = filteredReminders.filter((r) => !r.is_read && !r.notified);

            for (const r of newUnread) {
                let stickyMessage = "";
                if (r.related_model === 'amc.contract') {
                    stickyMessage = `AMC ${r.related_id?.[1]} ends on ${await this.convertToLocalTimeAsync(r.deadline)}`;
                } else if (r.name === 'Overdue Task Reminder' || r.is_overdue_reminder || r.action_domain) {
                    stickyMessage = "You have overdue tasks.";
                } else if (r.task_id) {
                    const deadlineFormatted = await this.convertToLocalTimeAsync(r.task_deadline);
                    stickyMessage = `Task ${r.task_id[1]} is due at ${deadlineFormatted}.`;
                } else if (r.activity_id) {
                    const summary = r.summary || "No Summary";
                    const date = r.date_deadline || "No Date";
                    const time = r.char_time || "No Time";
                    stickyMessage = `Activity ${summary} is due at ${date} (${time}).`;
                } else {
                    stickyMessage = r.message || r.name || "Reminder notification.";
                }

                // Mark as notified (for future sessions / reloads)
                await this.orm.call('task.reminder', 'write', [[r.id], { notified: true }]);
            }
            // Process reminders with async timezone conversion
            const processedReminders = await Promise.all(
                reminders.map(async (r) => {
                    let message = "";
                    let iconClass = "";
                    let isClickable = true;
                    let isOverdueReminder = false;
                    let isAMCReminder = false;

                    // Convert deadline to local time once
                    const localDeadline = await this.convertToLocalTimeAsync(r.deadline);

                    // Check if this is an AMC contract reminder
                    if (r.related_model === 'amc.contract') {
                        message = `AMC ${r.related_id[1]} ends on ${localDeadline}`; // Detailed message only
                        iconClass = 'amc.contract';
                        isClickable = true;
                        isAMCReminder = true;
                    }
                    // Check if this is an overdue reminder
                    else if (r.name === 'Overdue Task Reminder' || r.is_overdue_reminder || r.action_domain) {
                        message = "Click to view overdue tasks";
                        iconClass = 'overdue.task';
                        isClickable = true;
                        isOverdueReminder = true;
                    } else if (r.task_id) {
                        // Task reminder message format
                        const deadlineFormatted = await this.convertToLocalTimeAsync(r.task_deadline);
                        message = `Task ${r.task_id[1]} is due at ${deadlineFormatted}.`;
                        iconClass = 'project.task';
                        isClickable = true;
                    } else if (r.activity_id) {
                        const summary = r.summary || 'No Summary';
                        const rawDate = r.date_deadline || null;
                        const floatTime = r.char_time;

                        // Convert date format: yyyy-mm-dd → dd-mm-yyyy
                        let formattedDate = 'No Date';
                        if (rawDate) {
                            const dateObj = new Date(rawDate);
                            const day = dateObj.getDate().toString().padStart(2, '0');
                            const month = (dateObj.getMonth() + 1).toString().padStart(2, '0');
                            const year = dateObj.getFullYear();
                            formattedDate = `${day}-${month}-${year}`;
                        }
                        let formattedTime = 'No Time';
                        if (floatTime) {
                            // If it's already in "HH:mm" format, use it directly
                            if (typeof floatTime === 'string' && floatTime.includes(':')) {
                                formattedTime = floatTime;
                            } else {
                                // Fallback: try float parsing
                                const floatValue = parseFloat(floatTime);
                                const hours = Math.floor(floatValue);
                                const minutes = Math.round((floatValue - hours) * 60);
                                const paddedHours = hours.toString().padStart(2, '0');
                                const paddedMinutes = minutes.toString().padStart(2, '0');
                                formattedTime = `${paddedHours}:${paddedMinutes}`;
                            }
                        }
                        message = `Activity ${summary} is due at ${formattedDate} (${formattedTime}).`;
                        iconClass = 'mail.activity';
                        isClickable = true;
                    } else {
                        // Handle Day In/Out reminders or other types
                        message = r.message || r.name || "Reminder notification";
                        isClickable = false;
                    }
                    return {
                        id: r.id,
                        task_id: r.task_id?.[0],
                        name: r.name || '',
                        message: message,
                        project_name: r.project_id?.[1] || '',
                        date_display: localDeadline,
                        relative_time: this.convertToRelativeTime(r.deadline),
                        is_read: r.is_read || false,
                        icon_class: iconClass,
                        reminder_type: isAMCReminder
                                        ? 'AMC Contract Reminder: '
                                        : isOverdueReminder
                                            ? 'Overdue Tasks: '
                                            : r.activity_id
                                                ? r.name || 'Activity Reminder: No Type'
                                                : r.task_id
                                                    ? 'Task Reminder: '
                                                    : 'General Reminder: ',
                        deadline: r.deadline,
                        is_clickable: isClickable,
                        is_overdue_reminder: isOverdueReminder,
                        is_amc_reminder: isAMCReminder,
                        action_domain: r.action_domain,
                        related_model: r.related_model,
                        related_id: r.related_id?.[0],
                        related_name: r.related_id?.[1],
                    };
                })
            );
            // Update reminders with processed data
            this.state.reminders = processedReminders
                .sort((a, b) => new Date(b.effective_deadline) - new Date(a.effective_deadline));

            this.state.unreadCount = this.state.reminders.filter((r) => !r.is_read).length;
        } catch (error) {
            console.error("Failed to fetch reminders", error);
        }
    }

    toggleDropdown() {
        this.state.isOpen = !this.state.isOpen;

        if (this.state.isOpen) {
            // Add event listeners when opening
            setTimeout(() => {
                this.addEventListeners();
            }, 0);
            this.fetchReminders();
        } else {
            // Remove event listeners when closing
            this.removeEventListeners();
        }
    }

    async openNotifications() {
        await this.action.doAction("task_deadline_reminder.action_reminder_tasks");
        this.closeDropdown();
    }

    // ENHANCED: Handle different reminder types with specific actions
    async openReminder(reminderId, isClickable, event) {
        if (event) {
            event.stopPropagation();
        }
        try {
            const reminder = this.state.reminders.find(r => r.id === reminderId);

            // Check if this is an AMC contract reminder
            if (reminder && reminder.is_amc_reminder) {
                await this.openAMCContract(reminder);
            }
            // Check if this is an overdue task reminder
            else if (reminder && reminder.is_overdue_reminder) {
                await this.openOverdueTasksList(reminder);
            } else {
                // Handle regular task/activity reminders
                const action = await this.orm.call('task.reminder', 'get_formview_action', [[reminderId]]);
                await this.action.doAction(action);
            }

            // Mark as read when opened
            await this.orm.call('task.reminder', 'mark_as_read_for_user', [[reminderId]]);
            this.closeDropdown();

            // Refresh reminders after marking as read
            await this.fetchReminders();
        } catch (error) {
            console.error("Failed to open reminder", error);
        }
    }

    // NEW: Method to handle overdue tasks list view
    async openOverdueTasksList(reminder) {
        try {
            let domain = [];

            // Parse the domain from action_domain field
            if (reminder.action_domain) {
                try {
                    domain = JSON.parse(reminder.action_domain.replace(/'/g, '"'));
                } catch (parseError) {
                    console.warn("Failed to parse action_domain, using eval:", parseError);
                    try {
                        domain = eval(reminder.action_domain);
                    } catch (evalError) {
                        console.error("Failed to parse domain:", evalError);
                        // Fallback domain for overdue tasks
                        const today = new Date().toISOString().split('T')[0];
                        domain = [
                            ['date_deadline', '<', today],
                            ['stage_id.fold', '=', false],
                            ['active', '=', true]
                        ];
                    }
                }
            } else {
                // Default domain for overdue tasks
                const today = new Date().toISOString().split('T')[0];
                domain = [
                    ['date_deadline', '<', today],
                    ['stage_id.fold', '=', false],
                    ['active', '=', true]
                ];
            }

            // Create action to open overdue tasks tree view
            const action = {
                type: 'ir.actions.act_window',
                name: 'Overdue Tasks',
                res_model: 'project.task',
                view_mode: 'tree,form',
                views: [[false, 'tree'], [false, 'form']],
                domain: domain,
                target: 'current',
                context: {
                    'default_user_id': this.env.services.user.userId,
                    'search_default_overdue': 1,
                    'create': false, // Disable create button if needed
                }
            };

            await this.action.doAction(action);
            console.log("Overdue tasks tree view opened successfully");

        } catch (error) {
            console.error("Failed to open overdue tasks list:", error);

            // Fallback: Try to call backend method
            try {
                const backendAction = await this.orm.call('task.reminder', 'get_overdue_tasks_action', [[reminder.id]]);
                await this.action.doAction(backendAction);
            } catch (backendError) {
                console.error("Backend fallback also failed:", backendError);
            }
        }
    }

    async markAsRead(reminderId, event) {
        event.stopPropagation();
        try {
            await this.orm.call('task.reminder', 'mark_as_read_for_user', [[reminderId]]);
            this.fetchReminders(); // Refresh reminders list
        } catch (error) {
            console.error("Failed to mark reminder as read", error);
        }
    }

    switchTab(tabName, event) {
        event.stopPropagation(); // Prevent event bubbling
        this.state.activeTab = tabName;
    }

    // Get filtered reminders based on active tab and user-specific read status
    getFilteredReminders() {
        switch (this.state.activeTab) {
            case 'unread':
                return this.state.reminders.filter(r => !r.is_read);
            case 'read':
                return this.state.reminders.filter(r => r.is_read);
            case 'all':
            default:
                return this.state.reminders;
        }
    }
    async markAllAsRead(event) {
        event.stopPropagation();
        try {
            // Get all unread reminder IDs
            const unreadReminderIds = this.state.reminders
                .filter(r => !r.is_read)
                .map(r => r.id);

            if (unreadReminderIds.length > 0) {
                await this.orm.call(
                    'task.reminder',
                    'mark_as_read_for_user',
                    [unreadReminderIds]
                );
                // Refresh the reminders list
                await this.fetchReminders();
            }
        } catch (error) {
            console.error("Failed to mark all reminders as read", error);
        }
    }
}
NotificationSystray.template = "systray_notification_icon";

registry.category("systray").add("NotificationSystray", {
    Component: NotificationSystray,
    sequence: 125, // Puts it after the clock
});

