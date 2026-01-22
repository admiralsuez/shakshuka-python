// Analytics Extras: Strike Calendar + Daily Recap

(function () {
    'use strict';

    function getActiveAnalyticsRoot() {
        return document.querySelector('#analytics-page.page.active') || document.getElementById('analytics-page');
    }

    function qIn(root, selector) {
        return root ? root.querySelector(selector) : null;
    }

    async function requestJson(url, options = {}) {
        try {
            if (typeof window.apiCall === 'function') {
                const resp = await window.apiCall(url, options);
                return await resp.json();
            }

            const headers = { ...(options.headers || {}) };
            if (!('Content-Type' in headers)) headers['Content-Type'] = 'application/json';

            const resp = await fetch(url, {
                ...options,
                credentials: 'include',
                headers,
            });
            return await resp.json();
        } catch (e) {
            return null;
        }
    }

    function openModal(modalEl) {
        if (!modalEl) return;
        // Some parts of the app close modals by setting display:none.
        // Ensure opening reverses that so the modal is actually visible.
        modalEl.style.display = 'flex';
        modalEl.classList.add('active');
    }

    function closeModal(modalEl) {
        if (!modalEl) return;
        modalEl.classList.remove('active');
        modalEl.style.display = 'none';
    }

    function formatLocalDate(d) {
        const yy = d.getFullYear();
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const dd = String(d.getDate()).padStart(2, '0');
        return `${yy}-${mm}-${dd}`;
    }

    function monthToLabel(monthStr) {
        // monthStr: YYYY-MM
        try {
            const [y, m] = monthStr.split('-').map(Number);
            const d = new Date(y, (m || 1) - 1, 1);
            return d.toLocaleString(undefined, { month: 'long', year: 'numeric' });
        } catch (e) {
            return monthStr;
        }
    }

    function addMonths(monthStr, delta) {
        try {
            const [y, m] = monthStr.split('-').map(Number);
            const d = new Date(y, (m || 1) - 1, 1);
            d.setMonth(d.getMonth() + delta);
            const yy = d.getFullYear();
            const mm = String(d.getMonth() + 1).padStart(2, '0');
            return `${yy}-${mm}`;
        } catch (e) {
            return monthStr;
        }
    }

    function getCurrentMonthStr() {
        const now = new Date();
        return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
    }

    function buildMonthGrid(monthStr, dayCounts, maxCount) {
        const [y, m] = monthStr.split('-').map(Number);
        const year = y;
        const monthIndex = (m || 1) - 1;

        const first = new Date(year, monthIndex, 1);
        const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();

        // Sunday=0..Saturday=6
        const leading = first.getDay();

        const cells = [];
        for (let i = 0; i < leading; i++) {
            cells.push({ date: null, count: 0, dayNumber: null });
        }
        for (let day = 1; day <= daysInMonth; day++) {
            const d = `${year}-${String(m).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
            const c = Number(dayCounts && dayCounts[d] ? dayCounts[d] : 0);
            cells.push({ date: d, count: c, dayNumber: day });
        }

        // Pad trailing to complete the last week
        while (cells.length % 7 !== 0) {
            cells.push({ date: null, count: 0, dayNumber: null });
        }

        const buckets = (count) => {
            if (!count || count <= 0) return 0;
            if (maxCount <= 0) return 1;
            // 4 non-zero levels
            const ratio = count / Math.max(1, maxCount);
            if (ratio <= 0.25) return 1;
            if (ratio <= 0.5) return 2;
            if (ratio <= 0.75) return 3;
            return 4;
        };

        return cells.map(c => ({ ...c, level: buckets(c.count) }));
    }

    const StrikeCalendar = {
        _month: null,
        _monthsAvailable: [],
        _initialized: false,

        async init() {
            if (this._initialized) return;
            this._initialized = true;

            const root = getActiveAnalyticsRoot();
            const prevBtn = qIn(root, '#strike-cal-prev');
            const nextBtn = qIn(root, '#strike-cal-next');
            if (prevBtn) prevBtn.addEventListener('click', () => this.goPrev());
            if (nextBtn) nextBtn.addEventListener('click', () => this.goNext());

            // Initial load best-effort
            await this.load(getCurrentMonthStr());
        },

        async load(monthStr) {
            const root = getActiveAnalyticsRoot();
            const gridEl = qIn(root, '#strike-cal-grid');
            const monthEl = qIn(root, '#strike-cal-month');
            if (!gridEl || !monthEl) return;

            this._month = monthStr || getCurrentMonthStr();
            monthEl.textContent = monthToLabel(this._month);

            const payload = await requestJson(`/api/analytics/strike-calendar?month=${encodeURIComponent(this._month)}`);

            const ok = payload && payload.success;
            const days = (ok && payload.days) ? payload.days : {};
            const added = (ok && payload.added) ? payload.added : {};
            const max = (ok && typeof payload.max === 'number') ? payload.max : 0;
            this._monthsAvailable = (ok && Array.isArray(payload.months)) ? payload.months : [];

            const cells = buildMonthGrid(this._month, days, max);

            gridEl.innerHTML = '';
            cells.forEach(cell => {
                const el = document.createElement('div');
                el.className = `strike-cal-cell lvl${cell.level}`;
                if (cell.date) {
                    const struckCount = Number(cell.count || 0);
                    const addedCount = Number(added && added[cell.date] ? added[cell.date] : 0);
                    el.title = `${cell.date}\nStriked: ${struckCount}\nNew tasks: ${addedCount}`;
                    el.setAttribute('data-day', cell.date);
                    const label = document.createElement('span');
                    label.className = 'strike-cal-day';
                    label.textContent = String(cell.dayNumber || '');
                    el.appendChild(label);
                } else {
                    el.style.visibility = 'hidden';
                }
                gridEl.appendChild(el);
            });

            this._updateNavButtons();
        },

        _updateNavButtons() {
            const root = getActiveAnalyticsRoot();
            const prevBtn = qIn(root, '#strike-cal-prev');
            const nextBtn = qIn(root, '#strike-cal-next');
            const currentMonth = getCurrentMonthStr();

            const prev = addMonths(this._month, -1);
            const next = addMonths(this._month, 1);

            // Disable next if it goes beyond current month.
            if (nextBtn) {
                nextBtn.disabled = next > currentMonth;
            }

            // Always allow going back in time.
            if (prevBtn) {
                prevBtn.disabled = false;
            }
        },

        async goPrev() {
            const prev = addMonths(this._month || getCurrentMonthStr(), -1);
            await this.load(prev);
        },

        async goNext() {
            const next = addMonths(this._month || getCurrentMonthStr(), 1);
            await this.load(next);
        }
    };

    const DailyRecap = {
        _initialized: false,
        _modal: null,
        _recapDay: null,
        _showNowPromise: null,

        init() {
            if (this._initialized) return;
            this._initialized = true;

            this._modal = document.getElementById('daily-recap-modal');
            const closeBtn = document.getElementById('close-daily-recap-modal');
            const dismissBtn = document.getElementById('daily-recap-dismiss');
            if (closeBtn) closeBtn.addEventListener('click', () => this.dismiss());
            if (dismissBtn) dismissBtn.addEventListener('click', () => this.dismiss());
            if (this._modal) {
                this._modal.addEventListener('click', (e) => {
                    if (e.target === this._modal) this.dismiss();
                });
            }
        },

        _ensureModal() {
            // Always re-query if null (handles SPA timing issues)
            if (!this._modal) {
                this._modal = document.getElementById('daily-recap-modal');
            }
            return this._modal;
        },

        _getResetTime() {
            try {
                const s = (AppState && AppState.get) ? (AppState.get('currentSettings') || {}) : {};
                return String(s.daily_reset_time || '06:00');
            } catch (e) {
                return '06:00';
            }
        },

        _isAfterReset(now) {
            try {
                const t = this._getResetTime();
                const [hh, mm] = t.split(':').map(Number);
                const reset = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hh || 0, mm || 0, 0, 0);
                return now >= reset;
            } catch (e) {
                return false;
            }
        },

        _yesterdayStr(now) {
            const d = new Date(now);
            d.setDate(d.getDate() - 1);
            // Use local date to avoid UTC day shifting (e.g., IST users).
            return formatLocalDate(d);
        },

        async maybeShowOnLogin() {
            return this.maybeShowOnStartup();
        },

        async maybeShowOnStartup() {
            console.log('[DailyRecap] maybeShowOnStartup called');
            this.init();

            const now = new Date();
            if (!this._isAfterReset(now)) {
                console.log('[DailyRecap] Not after reset time, skipping');
                return;
            }

            const recapDay = this._yesterdayStr(now);
            console.log('[DailyRecap] Checking recap for day:', recapDay);

            const payload = await requestJson(`/api/analytics/daily-recap?day=${encodeURIComponent(recapDay)}`);
            if (!payload || !payload.success) {
                console.log('[DailyRecap] No valid payload');
                return;
            }
            if (payload.seen) {
                console.log('[DailyRecap] Already seen, skipping');
                return;
            }

            console.log('[DailyRecap] Showing recap modal');
            this._render(payload);
            const modal = this._ensureModal();
            if (!modal) {
                console.error('[DailyRecap] Modal element not found!');
                return;
            }
            openModal(modal);

            // Mark seen immediately when shown so restart won't show again.
            try {
                await this._markSeen(payload.day);
            } catch (e) { /* no-op */ }
        },

        async showNow() {
            // Manual trigger (ignores "seen" guard) for Settings button.
            console.log('[DailyRecap] showNow called');
            if (this._showNowPromise) {
                console.log('[DailyRecap] Already showing, returning existing promise');
                return this._showNowPromise;
            }

            this._showNowPromise = (async () => {
                this.init();

                const day = this._yesterdayStr(new Date());
                console.log('[DailyRecap] Manual trigger for day:', day);
                const payload = await requestJson(`/api/analytics/daily-recap?day=${encodeURIComponent(day)}`);
                if (!payload || !payload.success) {
                    console.log('[DailyRecap] No payload, showing empty recap');
                    this._render({
                        day,
                        tasks_striked: 0,
                        tasks_completed_forever: 0,
                        new_tasks_added: 0,
                        settings_changed: 0,
                        tasks_planned: 0,
                        notes_added: 0,
                        streak_days: 0,
                    });
                } else {
                    console.log('[DailyRecap] Rendering recap with payload');
                    this._render(payload);
                }
                const modal = this._ensureModal();
                if (!modal) {
                    console.error('[DailyRecap] Modal element not found!');
                    return;
                }
                console.log('[DailyRecap] Opening modal');
                openModal(modal);
            })()
                .finally(() => { this._showNowPromise = null; });

            return this._showNowPromise;
        },

        _render(payload) {
            // Format date as "Yesterday's Recap (17th December)"
            const title = document.getElementById('daily-recap-title');
            if (title && payload.day) {
                const d = new Date(payload.day + 'T00:00:00');
                const day = d.getDate();
                const suffix = day === 1 || day === 21 || day === 31 ? 'st' :
                              day === 2 || day === 22 ? 'nd' :
                              day === 3 || day === 23 ? 'rd' : 'th';
                const monthName = d.toLocaleDateString('en-US', { month: 'long' });
                title.textContent = `Yesterday's Recap (${day}${suffix} ${monthName})`;
            }

            // Streak info
            const streakDaysEl = document.getElementById('daily-recap-streak-days');
            if (streakDaysEl) streakDaysEl.textContent = `${payload.streak_days ?? 0} days`;

            // Stats grid (other metrics)
            const grid = document.getElementById('daily-recap-grid');
            if (!grid) return;

            const items = [
                { key: 'tasks_striked', label: 'Tasks striked', value: payload.tasks_striked ?? 0 },
                { key: 'tasks_completed_forever', label: 'Completed forever', value: payload.tasks_completed_forever ?? 0 },
                { key: 'new_tasks_added', label: 'New tasks added', value: payload.new_tasks_added ?? 0 },
                { key: 'tasks_retried', label: 'Tasks retried', value: payload.tasks_retried ?? 0 },
                { key: 'settings_changed', label: 'Settings changed', value: payload.settings_changed ?? 0 },
                { key: 'tasks_planned', label: 'Tasks planned', value: payload.tasks_planned ?? 0 },
                { key: 'notes_added', label: 'Notes added', value: payload.notes_added ?? 0 }
            ];

            grid.innerHTML = '';
            items.forEach(it => {
                const el = document.createElement('div');
                el.className = 'daily-recap-item';
                el.innerHTML = `<div class="label">${Utils && Utils.sanitizeHTML ? Utils.sanitizeHTML(it.label) : it.label}</div>` +
                    `<div class="value">${String(it.value)}</div>`;
                grid.appendChild(el);
            });

            this._recapDay = payload.day;
        },

        async _markSeen(day) {
            if (!day) return;
            try {
                if (typeof window.apiCall === 'function') {
                    await window.apiCall('/api/analytics/daily-recap/seen', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ day })
                    });
                } else {
                    await fetch('/api/analytics/daily-recap/seen', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        credentials: 'include',
                        body: JSON.stringify({ day })
                    });
                }
            } catch (e) {
                // best-effort
            }
        },

        async dismiss() {
            closeModal(this._modal);
            // Seen is now recorded when the recap is shown.
        }
    };

    const CompletedByMonth = {
        async refresh() {
            try {
                const root = getActiveAnalyticsRoot();
                const listEl = qIn(root, '#completed-by-month-list');
                if (!listEl) return;

                let tasks = [];
                try {
                    if (typeof AppState !== 'undefined' && typeof AppState.getTasks === 'function') {
                        tasks = AppState.getTasks() || [];
                    }
                } catch (e) { tasks = []; }

                if (!tasks.length) {
                    const payload = await requestJson('/api/tasks');
                    if (Array.isArray(payload)) tasks = payload;
                }

                const groups = {};
                tasks.forEach((t) => {
                    if (!t) return;
                    if (!(t.completed || t.struck_forever)) return;
                    if (!t.completed_at) return;
                    const s = String(t.completed_at);
                    const d = s.includes('T') ? s.split('T')[0] : s;
                    if (!d || d.length < 7) return;
                    const monthKey = d.slice(0, 7); // YYYY-MM
                    if (!groups[monthKey]) groups[monthKey] = 0;
                    groups[monthKey] += 1;
                });

                const months = Object.keys(groups).sort().reverse();
                listEl.innerHTML = '';
                if (!months.length) {
                    const empty = document.createElement('div');
                    empty.className = 'completed-month-empty';
                    empty.textContent = 'No completed tasks with dates yet';
                    listEl.appendChild(empty);
                    return;
                }

                months.forEach((m) => {
                    const btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'btn-secondary completed-month-btn';
                    btn.textContent = `${monthToLabel(m)} (${groups[m]})`;
                    btn.addEventListener('click', () => {
                        if (typeof window.openCompletedTasksForMonth === 'function') {
                            window.openCompletedTasksForMonth(m);
                        }
                    });
                    listEl.appendChild(btn);
                });
            } catch (e) {
                // no-op
            }
        },
    };

    window.AnalyticsExtras = {
        StrikeCalendar,
        DailyRecap,
        CompletedByMonth,
    };

    // Best-effort init for Analytics card (render if card exists)
    document.addEventListener('DOMContentLoaded', () => {
        try { StrikeCalendar.init(); } catch (e) { /* no-op */ }
        try { DailyRecap.init(); } catch (e) { /* no-op */ }
        try { CompletedByMonth.refresh(); } catch (e) { /* no-op */ }
    });
}());
