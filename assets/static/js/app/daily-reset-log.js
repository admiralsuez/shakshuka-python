(function () {
    'use strict';

    let currentLog = null;
    let loading = false;

    function getEl(id) {
        return document.getElementById(id);
    }

    function safeNotify(msg, type) {
        if (typeof window.showNotification === 'function') {
            window.showNotification(msg, type || 'info');
        }
    }

    async function fetchJson(url, options) {
        if (typeof window.fetchWithFallback === 'function') {
            return await window.fetchWithFallback(url, Object.assign({ fallbackValue: null, cacheTTL: 0 }, options || {}));
        }
        const resp = await fetch(url, Object.assign({ credentials: 'include' }, options || {}));
        const data = await resp.json().catch(() => null);
        if (!resp.ok) {
            const msg = data && (data.error || data.message) ? (data.error || data.message) : "Request failed";
            throw new Error(msg);
        }
        return data;
    }

    function updateIndicator() {
        const indicator = getEl('daily-reset-log-indicator');
        const countEl = getEl('daily-reset-log-count');
        const hasLog = !!(currentLog && currentLog.task_count > 0);

        if (indicator) {
            indicator.style.display = hasLog ? 'flex' : 'none';
        }
        if (countEl) {
            countEl.textContent = hasLog ? String(currentLog.task_count) : '0';
        }
    }

    function renderLogIntoModal() {
        const listEl = getEl('daily-reset-log-list');
        const subtitleEl = getEl('daily-reset-log-subtitle');

        if (!listEl || !subtitleEl) return;

        if (!currentLog) {
            subtitleEl.textContent = 'No recent daily reset to show.';
            listEl.innerHTML = '';
            return;
        }

        const when = currentLog.reset_at || '';
        const count = currentLog.task_count || 0;
        const reason = currentLog.reset_reason || 'scheduled';

        subtitleEl.textContent = `Last daily reset (${reason}) refreshed ${count} task${count === 1 ? '' : 's'}.`;

        const tasks = Array.isArray(currentLog.tasks) ? currentLog.tasks : [];
        if (!tasks.length) {
            listEl.innerHTML = '<p style="color: var(--text-secondary);">No task details available for this reset.</p>';
            return;
        }

        const rows = tasks.map((t) => {
            if (!t || typeof t !== 'object') return '';
            const title = String(t.title || '').trim() || 'Untitled task';
            const project = String(t.project || '').trim();
            const due = String(t.due_date || '').trim();
            const scheduled = String(t.scheduled_date || '').trim();
            const metaParts = [];
            if (project) metaParts.push(project);
            if (due) metaParts.push(`due ${due}`);
            if (scheduled) metaParts.push(`scheduled ${scheduled}`);
            if (typeof t.strike_count === 'number') {
                metaParts.push(`${t.strike_count} strike${t.strike_count === 1 ? '' : 's'}`);
            }
            const meta = metaParts.length ? metaParts.join(' • ') : '';

            return `
                <div class="daily-reset-log-item" style="padding: 10px; border-radius: 8px; border: 1px solid var(--border-color, rgba(0,0,0,0.08)); margin-bottom: 8px; background: var(--surface-color, #fff);">
                    <div style="font-weight: 600; color: var(--text-color, #333);">${escapeHtml(title)}</div>
                    ${meta ? `<div style="font-size: 12px; color: var(--text-secondary, #666); margin-top: 4px;">${escapeHtml(meta)}</div>` : ''}
                </div>
            `;
        }).filter(Boolean);

        listEl.innerHTML = rows.join('');
    }

    function openModal() {
        const modal = getEl('daily-reset-log-modal');
        if (!modal) return;
        modal.classList.add('active');
        modal.style.display = 'flex';
        renderLogIntoModal();
    }

    function closeModal() {
        const modal = getEl('daily-reset-log-modal');
        if (!modal) return;
        modal.classList.remove('active');
        modal.style.display = 'none';
    }

    async function loadLatestLog() {
        if (loading) return;
        loading = true;
        try {
            const data = await fetchJson('/api/tasks/reset-log');
            if (!data || !data.success || !data.log) {
                currentLog = null;
            } else {
                currentLog = data.log;
            }
            updateIndicator();
        } catch (e) {
            // Best-effort: if this fails, just hide indicator.
            currentLog = null;
            updateIndicator();
        } finally {
            loading = false;
        }
    }

    async function clearLogOnServer() {
        try {
            await fetchJson('/api/tasks/reset-log/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentLog && currentLog.id ? { id: currentLog.id } : {}),
            });
        } catch (e) {
            // Non-fatal; we still clear local indicator.
        }
        currentLog = null;
        updateIndicator();
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function bindUi() {
        const indicator = getEl('daily-reset-log-indicator');
        if (indicator) {
            indicator.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (!currentLog) {
                    await loadLatestLog();
                }
                if (currentLog) {
                    openModal();
                } else {
                    safeNotify('No recent daily reset found.', 'info');
                }
            });
        }

        const closeBtn = getEl('close-daily-reset-log-modal');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                // Close icon in header should only hide the dialog, not clear notifications.
                closeModal();
            });
        }

        const footerCloseBtn = getEl('daily-reset-log-close-btn');
        if (footerCloseBtn) {
            footerCloseBtn.addEventListener('click', () => {
                // Footer "Close" behaves like the header X: just close the dialog.
                closeModal();
            });
        }

        const dismissBtn = getEl('daily-reset-log-dismiss-btn');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', async () => {
                // Explicit dismissal clears the notification on the server and hides the indicator.
                await clearLogOnServer();
                closeModal();
            });
        }

        // Initial fetch once UI is ready.
        loadLatestLog().catch(() => {});
    }

    window.DailyResetLog = {
        refresh: () => loadLatestLog(),
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindUi);
    } else {
        bindUi();
    }
}());
