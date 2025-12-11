// Shared helpers for interpreting task state in a consistent way
// Exposed via window.TaskHelpers.

(function () {
    'use strict';

    function isDone(task) {
        if (!task) return false;
        return Boolean(task.completed || task.struck_forever);
    }

    function isStruckToday(task) {
        if (!task) return false;
        return Boolean(task.struck_today);
    }

    function _getTodayDateString() {
        try {
            const today = new Date();
            return today.toISOString().split('T')[0];
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
        const todayStr = _getTodayDateString();
        const due = _getDateOnly(task.due_date);
        if (!todayStr || !due) return false;
        return due < todayStr;
    }

    function isActive(task) {
        if (!task) return false;
        if (isDone(task) || isStruckToday(task)) return false;

        const todayStr = _getTodayDateString();
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