// Quick date helpers for due date buttons
function setQuickDate(kind) {
    const el = document.getElementById('task-due-date');
    if (!el) return;
    const today = new Date();
    let date = new Date(today);
    if (kind === 'today') {
        // date already today
    } else if (kind === 'tomorrow') {
        date.setDate(date.getDate() + 1);
    } else if (kind === 'thisweek') {
        const day = date.getDay(); // 0-6
        const diff = 6 - day; // go to Saturday as end of week
        date.setDate(date.getDate() + (diff > 0 ? diff : 0));
    }
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    el.value = `${yyyy}-${mm}-${dd}`;
}

// Helper: determine if a given date string is today (compares by date only)
function isDueToday(dueRaw) {
    if (!dueRaw) return false;
    try {
        const raw = String(dueRaw);
        const dateOnly = raw.split('T')[0];
        const today = new Date();
        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;
        return dateOnly === todayStr;
    } catch (e) {
        return false;
    }
}

// Human-friendly label for due dates used in task cards
function formatDueDateLabel(dueRaw) {
    if (!dueRaw) return '';
    try {
        const raw = String(dueRaw);
        const dateOnly = raw.split('T')[0];
        const dueDate = new Date(dateOnly + 'T00:00:00');
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const diffDays = Math.round((dueDate - today) / (1000 * 60 * 60 * 24));

        // Default (non-casual) formatting
        let settings = {};
        try {
            settings = (typeof AppState !== 'undefined' && AppState.get)
                ? (AppState.get('currentSettings') || {})
                : {};
        } catch (e) {
            settings = {};
        }

        const useCasual = !!settings.casual_dates;

        if (!useCasual) {
            // Non-casual mode: always show the raw YYYY-MM-DD date
            return dateOnly;
        }

        // Casual formatting
        if (diffDays === 0) return 'today';
        if (diffDays === 1) return 'tomorrow';
        if (diffDays === -1) return 'yesterday';
        if (diffDays < -1) return `${Math.abs(diffDays)} days ago`;

        // Weekend helpers (Saturday/Sunday)
        const todayDow = today.getDay(); // 0-6, Sunday=0
        const thisSaturday = new Date(today);
        thisSaturday.setDate(today.getDate() + ((6 - todayDow + 7) % 7));
        const thisSunday = new Date(thisSaturday);
        thisSunday.setDate(thisSaturday.getDate() + 1);

        const nextSaturday = new Date(thisSaturday);
        nextSaturday.setDate(thisSaturday.getDate() + 7);
        const nextSunday = new Date(nextSaturday);
        nextSunday.setDate(nextSaturday.getDate() + 1);

        const isSameDay = (d1, d2) => d1.getFullYear() === d2.getFullYear()
            && d1.getMonth() === d2.getMonth()
            && d1.getDate() === d2.getDate();

        if (isSameDay(dueDate, thisSaturday) || isSameDay(dueDate, thisSunday)) {
            return 'this weekend';
        }
        if (isSameDay(dueDate, nextSaturday) || isSameDay(dueDate, nextSunday)) {
            return 'next weekend';
        }

        if (diffDays > 1) {
            return `in ${diffDays} days`;
        }

        // For past dates or unexpected values, fall back to the raw date
        return dateOnly;
    } catch (e) {
        return String(dueRaw);
    }
}
