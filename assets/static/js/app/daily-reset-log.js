(function () {
    'use strict';

    let currentLog = null;
    let latestCleanerRun = null;
    let latestCompanionSync = null;
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
        const indicator = getEl('notifications-indicator');
        const countEl = getEl('notifications-count');

        const resetCount = currentLog && typeof currentLog.task_count === 'number' ? currentLog.task_count : 0;
        const cleanerCount = latestCleanerRun && typeof latestCleanerRun.cleaned_count === 'number'
            ? latestCleanerRun.cleaned_count
            : 0;

        const hasReset = resetCount > 0;
        const hasCleanerMessage = latestCleanerRun && cleanerCount > 0; // only show cleaner notification if it actually cleaned notes
        const hasCompanionSync = latestCompanionSync && (latestCompanionSync.count > 0);

        const totalNotifications = (hasReset ? 1 : 0) + (hasCleanerMessage ? 1 : 0) + (hasCompanionSync ? 1 : 0);
        const hasAny = totalNotifications > 0;

        if (indicator) {
            indicator.style.display = hasAny ? 'flex' : 'none';
        }
        if (countEl) {
            countEl.textContent = hasAny ? String(totalNotifications) : '0';
        }
    }

    function renderCompanionSyncSection() {
        const el = getEl('daily-reset-companion-sync');
        if (!el) return;
        if (!latestCompanionSync || !latestCompanionSync.count) {
            el.style.display = 'none';
            el.innerHTML = '';
            return;
        }
        const { count, deviceName, timestamp, tasks } = latestCompanionSync;
        const itemLabel = count === 1 ? '1 item' : `${count} items`;
        const hasTasks = Array.isArray(tasks) && tasks.length > 0;
        let html = `<div style="border:1px solid var(--border-color,rgba(0,0,0,0.1));border-radius:8px;overflow:hidden;margin-bottom:12px;">`
            + `<div style="display:flex;align-items:center;gap:10px;padding:10px 14px;background:var(--surface-color,#fff);">`
            + `<span style="font-size:18px;line-height:1;">&#128247;</span>`
            + `<div style="flex:1;min-width:0;">`
            + `<div style="font-weight:600;font-size:13px;color:var(--text-color);">Synced from ${escapeHtml(deviceName || 'Phone')} &mdash; ${itemLabel}</div>`
            + (timestamp ? `<div style="font-size:11px;color:var(--text-secondary);margin-top:1px;">at ${escapeHtml(timestamp)}</div>` : '')
            + `</div></div>`;
        if (hasTasks) {
            html += `<div style="padding:6px 14px 10px;display:flex;flex-direction:column;gap:4px;">`;
            html += tasks.map(t => {
                const title = escapeHtml(String(t.title || t.name || 'Untitled').trim());
                const proj = t.project ? `<span style="font-size:11px;color:var(--text-secondary);margin-left:6px;">&#183; ${escapeHtml(t.project)}</span>` : '';
                return `<div style="display:flex;align-items:baseline;padding:4px 8px;border-radius:5px;background:var(--bg-color,rgba(0,0,0,0.03));font-size:13px;">`
                    + `<span style="color:var(--text-secondary);margin-right:6px;font-size:11px;">&#9632;</span>${title}${proj}</div>`;
            }).join('');
            html += `</div>`;
        }
        html += `</div>`;
        el.innerHTML = html;
        el.style.display = 'block';
    }

    function renderLogIntoModal() {
        const listEl = getEl('daily-reset-log-list');
        const subtitleEl = getEl('daily-reset-log-subtitle');
        const secondaryEl = getEl('daily-reset-secondary');

        if (!listEl || !subtitleEl) return;

        const reset = currentLog;
        const cleaner = latestCleanerRun;

        if (!reset && !cleaner) {
            subtitleEl.textContent = 'No recent daily reset summary.';
            if (secondaryEl) secondaryEl.textContent = '';
            listEl.innerHTML = '';
            renderCompanionSyncSection();
            return;
        }

        if (reset) {
            const when = reset.reset_at || '';
            const count = reset.task_count || 0;
            const reason = reset.reset_reason || 'scheduled';
            subtitleEl.textContent = `Last daily reset (${reason}) refreshed ${count} task${count === 1 ? '' : 's'}.`;
        } else {
            subtitleEl.textContent = 'No recent daily reset summary.';
        }

        if (secondaryEl) {
            if (cleaner) {
                const cleaned = typeof cleaner.cleaned_count === 'number' ? cleaner.cleaned_count : 0;
                const ranAt = cleaner.ran_at || '';
                secondaryEl.textContent = `Note cleaner ran at ${ranAt} and cleaned ${cleaned} empty note${cleaned === 1 ? '' : 's'}.`;
            } else {
                secondaryEl.textContent = '';
            }
        }

        const tasks = reset && Array.isArray(reset.tasks) ? reset.tasks : [];

        // Split into struck tasks (the ones the user actually interacted with)
        // and tasks that were only unscheduled (no strikes → less interesting).
        const struckTasks = tasks.filter(t => t && typeof t === 'object' && typeof t.strike_count === 'number' && t.strike_count > 0);
        const unscheduledOnlyCount = tasks.length - struckTasks.length;

        // Append unscheduled-only count to subtitle so it is surfaced without cluttering the list.
        if (unscheduledOnlyCount > 0 && subtitleEl) {
            subtitleEl.textContent += ` ${unscheduledOnlyCount} task${unscheduledOnlyCount === 1 ? '' : 's'} unscheduled (not struck).`;
        }

        if (!struckTasks.length) {
            listEl.innerHTML = '<p style="color: var(--text-secondary);">No struck tasks in this reset.</p>';
            return;
        }

        const rows = struckTasks.map((t) => {
            if (!t || typeof t !== 'object') return '';
            const title = String(t.title || '').trim() || 'Untitled task';
            const project = String(t.project || '').trim();
            const due = String(t.due_date || '').trim();
            const metaParts = [];
            if (project) metaParts.push(project);
            if (due) metaParts.push(`due ${due}`);
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
        renderCompanionSyncSection();
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

            // Also fetch the latest note-cleaner summary if the endpoint exists.
            try {
                const cleanerData = await fetchJson('/api/notes/cleaner-status');
                if (cleanerData && cleanerData.success && cleanerData.status) {
                    latestCleanerRun = cleanerData.status;
                } else {
                    latestCleanerRun = null;
                }
            } catch (e) {
                // If the cleaner endpoint is missing or fails, ignore and keep existing value.
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
        // Only escape characters that are unsafe in HTML text content.
        // Single quotes are safe inside text nodes and do not need encoding.
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function bindUi() {
        const indicator = getEl('notifications-indicator');
        if (indicator) {
            indicator.addEventListener('click', async (e) => {
                e.preventDefault();
                e.stopPropagation();
                if (!currentLog) {
                    await loadLatestLog();
                }
                if (currentLog || latestCompanionSync) {
                    openModal();
                } else {
                    safeNotify('No recent notifications found.', 'info');
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
        addCompanionSync: (info) => {
            // info: { count, deviceName, timestamp, tasks[] }
            latestCompanionSync = info || null;
            updateIndicator();
            // Re-render companion section if modal is currently open
            const modal = getEl('daily-reset-log-modal');
            if (modal && (modal.classList.contains('active') || modal.style.display === 'flex')) {
                renderCompanionSyncSection();
            }
        },
        clearCompanionSync: () => {
            latestCompanionSync = null;
            updateIndicator();
        },
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindUi);
    } else {
        bindUi();
    }
}());
