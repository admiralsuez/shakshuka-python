(function () {
    'use strict';

    let currentPendingSubmissionId = null;
    let pollingTimer = null;
    let pollingInFlight = false;

    function getEl(id) {
        return document.getElementById(id);
    }

    function open(id) {
        if (typeof window.openModal === 'function') {
            window.openModal(id);
            return;
        }
        const el = getEl(id);
        if (el) {
            el.classList.add('active');
            el.style.display = 'flex';
        }
    }

    function close(id) {
        if (typeof window.closeModal === 'function') {
            window.closeModal(id);
            return;
        }
        const el = getEl(id);
        if (el) {
            el.classList.remove('active');
            el.style.display = 'none';
        }
    }

    async function fetchJson(url, options) {
        if (typeof fetchWithFallback === 'function') {
            return await fetchWithFallback(url, Object.assign({ fallbackValue: null, cacheTTL: 0 }, options || {}));
        }
        const resp = await fetch(url, Object.assign({ credentials: 'include' }, options || {}));
        const data = await resp.json().catch(() => null);
        if (!resp.ok) {
            const msg = data && (data.error || data.message) ? (data.error || data.message) : `HTTP ${resp.status}`;
            throw new Error(msg);
        }
        return data;
    }

    function safeNotify(msg, type) {
        if (typeof showNotification === 'function') {
            showNotification(msg, type || 'info');
        }
    }

    function clearQr() {
        const qrEl = getEl('pair-phone-qr');
        if (qrEl) {
            qrEl.innerHTML = '';
        }
    }

    function renderQr(text) {
        const qrEl = getEl('pair-phone-qr');
        if (!qrEl) return;

        clearQr();

        try {
            if (typeof QRCode === 'function') {
                // eslint-disable-next-line no-new
                new QRCode(qrEl, {
                    text,
                    width: 220,
                    height: 220
                });
            }
        } catch (e) {
            // no-op
        }
    }

    async function refreshPairingCode() {
        const statusEl = getEl('pair-phone-status');
        const codeEl = getEl('pair-phone-code');
        const urlEl = getEl('pair-phone-url');

        if (statusEl) statusEl.textContent = 'Loading…';
        if (codeEl) codeEl.textContent = '';
        if (urlEl) urlEl.textContent = '';
        clearQr();

        try {
            const data = await fetchJson('/api/mobile/pairing');
            if (!data || !data.success) {
                throw new Error((data && data.error) ? data.error : 'Failed to create pairing code');
            }

            const code = String(data.code || '').trim();
            const lanUrl = data.lan_url || '';

            if (statusEl) statusEl.textContent = 'Scan this QR in your phone app or enter the code manually.';
            if (codeEl) codeEl.textContent = code;
            if (urlEl) urlEl.textContent = lanUrl;

            const qrPayload = JSON.stringify({ url: lanUrl, code });
            renderQr(qrPayload);
        } catch (e) {
            if (statusEl) statusEl.textContent = e.message || 'Failed to create pairing code';
        }
    }

    function openPairPhoneModal() {
        open('pair-phone-modal');
        refreshPairingCode();
    }

    function getTasksFromPayload(payload) {
        if (!payload || typeof payload !== 'object') return [];
        const tasks = payload.tasks;
        return Array.isArray(tasks) ? tasks : [];
    }

    function renderInboxList(submission) {
        const listEl = getEl('mobile-inbox-list');
        const subtitleEl = getEl('mobile-inbox-subtitle');

        if (!listEl) return;

        const payload = submission.payload || null;
        const tasks = getTasksFromPayload(payload);
        const deviceName = submission.device_name || (payload && payload.device_name) || 'Phone';

        if (subtitleEl) {
            subtitleEl.textContent = `${deviceName} wants to add ${tasks.length} task(s). Select what to import.`;
        }

        const html = [];
        html.push('<div style="display:flex; flex-direction:column; gap:10px;">');

        tasks.forEach((t) => {
            if (!t || typeof t !== 'object') return;
            const id = String(t.client_task_id || t.id || '').trim();
            const title = String(t.title || t.name || '').trim();
            const project = String(t.project || '').trim();
            const due = String(t.due_date || t.date || '').trim();
            const dur = (t.estimated_duration != null ? t.estimated_duration : t.duration);

            if (!id) return;

            const metaParts = [];
            if (project) metaParts.push(project);
            if (due) metaParts.push(due);
            if (dur != null && dur !== '') metaParts.push(`${dur}m`);
            const meta = metaParts.length ? metaParts.join(' • ') : '';

            html.push(`
                <label class="mobile-inbox-task-item" style="display:flex; gap:12px; align-items:center; padding:12px; border:1px solid var(--border-color,rgba(0,0,0,0.1)); border-radius:10px; cursor:pointer; background:var(--surface-color,#fff);">
                    <span class="custom-checkbox">
                        <input type="checkbox" class="mobile-inbox-task" data-task-id="${id}" checked />
                        <span class="checkmark"></span>
                    </span>
                    <div style="display:flex; flex-direction:column; gap:4px; flex:1;">
                        <div style="font-weight:600; color:var(--text-color,#333);">${escapeHtml(title || 'Untitled')}</div>
                        ${meta ? `<div style="opacity:0.7; font-size:12px; color:var(--text-secondary,#666);">${escapeHtml(meta)}</div>` : ''}
                    </div>
                </label>
            `);
        });

        html.push('</div>');
        listEl.innerHTML = html.join('');
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    async function pollInboxOnce() {
        if (pollingInFlight) return;
        pollingInFlight = true;

        try {
            const data = await fetchJson('/api/mobile/inbox/pending', { cacheTTL: 0 });
            if (!data || !data.success) return;

            const pending = data.pending;
            if (!pending || !pending.id) {
                currentPendingSubmissionId = null;
                return;
            }

            if (currentPendingSubmissionId === pending.id) {
                return;
            }

            currentPendingSubmissionId = pending.id;
            renderInboxList(pending);
            open('mobile-inbox-modal');
        } catch (e) {
            // no-op
        } finally {
            pollingInFlight = false;
        }
    }

    async function approveInbox() {
        const submissionId = currentPendingSubmissionId;
        if (!submissionId) return;

        const checkboxes = Array.from(document.querySelectorAll('.mobile-inbox-task'));
        const selected = checkboxes
            .filter(cb => cb && cb.checked)
            .map(cb => cb.getAttribute('data-task-id'))
            .filter(Boolean);

        try {
            const data = await fetchJson(`/api/mobile/inbox/${encodeURIComponent(submissionId)}/approve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_task_ids: selected })
            });

            if (!data || !data.success) {
                throw new Error((data && data.error) ? data.error : 'Failed to import tasks');
            }

            close('mobile-inbox-modal');
            currentPendingSubmissionId = null;

            const created = data.created != null ? data.created : 0;
            safeNotify(`Imported ${created} task(s)`, 'success');

            try {
                if (typeof loadTasks === 'function') {
                    await loadTasks();
                } else if (window.Tasks && typeof window.Tasks.loadTasks === 'function') {
                    await window.Tasks.loadTasks();
                }
            } catch (e) {
                // no-op
            }

            try {
                if (typeof updateDashboardStats === 'function') {
                    updateDashboardStats();
                }
            } catch (e) {
                // no-op
            }

        } catch (e) {
            safeNotify(e.message || 'Failed to import tasks', 'error');
        }
    }

    async function rejectInbox() {
        const submissionId = currentPendingSubmissionId;
        if (!submissionId) {
            close('mobile-inbox-modal');
            return;
        }

        try {
            const data = await fetchJson(`/api/mobile/inbox/${encodeURIComponent(submissionId)}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            });

            if (!data || !data.success) {
                throw new Error((data && data.error) ? data.error : 'Failed to reject');
            }

            close('mobile-inbox-modal');
            currentPendingSubmissionId = null;
        } catch (e) {
            safeNotify(e.message || 'Failed to reject', 'error');
        }
    }

    function startPolling() {
        if (pollingTimer) return;
        pollingTimer = window.setInterval(pollInboxOnce, 2500);
        pollInboxOnce();
    }

    function bindUi() {
        const pairBtn = getEl('pair-phone-btn');
        if (pairBtn) {
            pairBtn.addEventListener('click', openPairPhoneModal);
        }

        const pairCloseX = getEl('close-pair-phone-modal');
        if (pairCloseX) {
            pairCloseX.addEventListener('click', () => close('pair-phone-modal'));
        }

        const pairCloseBtn = getEl('pair-phone-close-btn');
        if (pairCloseBtn) {
            pairCloseBtn.addEventListener('click', () => close('pair-phone-modal'));
        }

        const pairRefreshBtn = getEl('pair-phone-refresh-btn');
        if (pairRefreshBtn) {
            pairRefreshBtn.addEventListener('click', refreshPairingCode);
        }

        const inboxCloseX = getEl('close-mobile-inbox-modal');
        if (inboxCloseX) {
            inboxCloseX.addEventListener('click', () => close('mobile-inbox-modal'));
        }

        const inboxApprove = getEl('mobile-inbox-approve-btn');
        if (inboxApprove) {
            inboxApprove.addEventListener('click', approveInbox);
        }

        const inboxReject = getEl('mobile-inbox-reject-btn');
        if (inboxReject) {
            inboxReject.addEventListener('click', rejectInbox);
        }

        startPolling();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindUi);
    } else {
        bindUi();
    }
})();
