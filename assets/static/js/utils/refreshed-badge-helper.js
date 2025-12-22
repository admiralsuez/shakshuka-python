/**
 * Refreshed Badge Helper
 * Determines if a task should show the "refreshed" badge (8am-12pm only)
 */

const RefreshedBadgeHelper = {
    /**
     * Check if current time is within badge display window (8am-12pm)
     */
    isWithinBadgeWindow() {
        const now = new Date();
        const hour = now.getHours();
        return hour >= 8 && hour < 12;
    },

    /**
     * Check if task was refreshed today
     */
    wasRefreshedToday(task) {
        if (!task || !task.refreshed_at) {
            return false;
        }

        try {
            const refreshedDate = new Date(task.refreshed_at);
            const today = new Date();
            
            // Check if refreshed_at is today
            return refreshedDate.getFullYear() === today.getFullYear() &&
                   refreshedDate.getMonth() === today.getMonth() &&
                   refreshedDate.getDate() === today.getDate();
        } catch (e) {
            return false;
        }
    },

    /**
     * Check if task should show refreshed badge
     */
    shouldShowBadge(task) {
        return this.isWithinBadgeWindow() && this.wasRefreshedToday(task);
    },

    /**
     * Get badge HTML for a task
     */
    getBadgeHTML(task) {
        if (!this.shouldShowBadge(task)) {
            return '';
        }

        return '<span class="task-refreshed-badge" title="Task refreshed from yesterday">Refreshed</span>';
    }
};

// Export globally
window.RefreshedBadgeHelper = RefreshedBadgeHelper;
