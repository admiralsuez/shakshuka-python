// Shared helpers for interpreting task state in a consistent way
// Exposed via window.TaskHelpers.

(function () {
    'use strict';

    function _formatLocalDate(d) {
        const yy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yy}-${mm}-${dd}`;
    }

    function isDone(task) {
        if (!task) return false;
        // Treat "strike for today" as completed for UI purposes until daily reset.
        return Boolean(task.completed || task.struck_forever || task.struck_today);
    }

    function isStruckToday(task) {
        if (!task) return false;
        return Boolean(task.struck_today);
    }

    function _getTodayDateString() {
        try {
            const today = new Date();
            return _formatLocalDate(today);
        } catch (e) {
            return null;
        }
    }

    function _getDateOnly(raw) {
        if (!raw) return null;
        const s = String(raw);
        return s.includes('T') ? s.split('T')[0] : s;
    }

    function isExpired(task) {
        if (!task || !task.due_date) return false;
        // Completed or struck forever tasks are not expired
        if (task.completed || task.struck_forever) return false;
        const todayStr = _getTodayDateString();
        const due = _getDateOnly(task.due_date);
        if (!todayStr || !due) return false;
        return due < todayStr;
    }

    function isActive(task) {
        if (!task) return false;
        if (isDone(task) || isStruckToday(task)) return false;

        const todayStr = _getTodayDateString();

        // Respect snoozed_until ("hide task for X days"). If the task is
        // snoozed to a future day, it should not appear as active until that
        // date has passed.
        if (task.snoozed_until && todayStr) {
            const snooze = _getDateOnly(task.snoozed_until);
            if (snooze && snooze > todayStr) return false;
        }

        const due = _getDateOnly(task.due_date);
        if (!todayStr || !due) return true; // no due date => active

        // Active if due today or later
        return due >= todayStr;
    }

    window.TaskHelpers = {
        isDone,
        isStruckToday,
        isExpired,
        isActive,
    };
})();