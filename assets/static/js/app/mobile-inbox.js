(function () {
    'use strict';

    let currentPendingSubmissionId = null;
    let pollingTimer = null;
    let pollingInFlight = false;
    let operationInProgress = false;

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

    function clearWebCompanionQr() {
        const qrEl = getEl('web-companion-qr');
        if (qrEl) {
            qrEl.innerHTML = '';
        }
    }

    function renderWebCompanionQr(url) {
        const qrEl = getEl('web-companion-qr');
        if (!qrEl) return;

        clearWebCompanionQr();

        try {
            if (typeof QRCode === 'function') {
                // eslint-disable-next-line no-new
                new QRCode(qrEl, {
                    text: url,
                    width: 180,
                    height: 180,
                    colorDark: '#ffffff',
                    colorLight: 'transparent',
                    correctLevel: QRCode.CorrectLevel.M,
                });
            }
        } catch (e) {
            // ignore
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

    let qrRefreshTimer = null;

    async function refreshPairingCode() {
        const statusEl = getEl('pair-phone-status');
        const codeEl = getEl('pair-phone-code');
        const urlEl = getEl('pair-phone-url');

        if (statusEl) statusEl.textContent = 'Loading…';
        if (codeEl) codeEl.textContent = '';
        if (urlEl) urlEl.textContent = '';
        clearQr();

        // Clear any existing auto-refresh timer
        if (qrRefreshTimer) {
            clearTimeout(qrRefreshTimer);
            qrRefreshTimer = null;
        }

        try {
            const data = await fetchJson('/api/mobile/pairing');
            if (!data || !data.success) {
                throw new Error((data && data.error) ? data.error : 'Failed to create pairing code');
            }

            const code = String(data.code || '').trim();
            const lanUrl = data.lan_url || '';
            const expiresIn = data.expires_in || 300; // Default 5 minutes

            if (statusEl) statusEl.textContent = 'Scan this QR in your phone app or enter the code manually.';
            if (codeEl) codeEl.textContent = code;
            if (urlEl) urlEl.textContent = lanUrl;

            // Update web companion URL for iPhone/other devices
            const webCompanionUrlEl = getEl('web-companion-url');
            if (webCompanionUrlEl && lanUrl) {
                // Extract base URL (without /api/mobile/pair path) and add /companion
                try {
                    const urlObj = new URL(lanUrl);
                    const companionUrl = `${urlObj.protocol}//${urlObj.host}/companion`;
                    webCompanionUrlEl.textContent = companionUrl;
                    webCompanionUrlEl.dataset.url = companionUrl;

                    renderWebCompanionQr(companionUrl);
                } catch (e) {
                    webCompanionUrlEl.textContent = 'Could not determine URL';
                    clearWebCompanionQr();
                }
            }

            const qrPayload = JSON.stringify({ url: lanUrl, code });
            renderQr(qrPayload);

            // Auto-refresh QR code before expiry (refresh 30 seconds before expiry)
            const refreshDelay = Math.max((expiresIn - 30) * 1000, 30000);
            qrRefreshTimer = setTimeout(() => {
                // Only refresh if modal is still open
                const modal = getEl('pair-phone-modal');
                if (modal && (modal.classList.contains('active') || modal.style.display === 'flex')) {
                    refreshPairingCode();
                }
            }, refreshDelay);

        } catch (e) {
            if (statusEl) statusEl.textContent = e.message || 'Failed to create pairing code';
        }
    }

    function openPairPhoneModal() {
        open('pair-phone-modal');
        loadPairedDevices();
        refreshPairingCode();
    }

    async function loadPairedDevices() {
        const section = getEl('paired-devices-section');
        const listEl = getEl('paired-devices-list');
        if (!section || !listEl) return;

        try {
            const response = await apiCall('/api/mobile/devices');
            const data = await response.json();
            
            if (data.success && data.devices && data.devices.length > 0) {
                section.style.display = 'block';
                const html = data.devices.map(device => {
                    const lastSeen = device.last_seen_at ? new Date(device.last_seen_at).toLocaleString() : 'Never';
                    return `
                        <div class="paired-device-item" style="display: flex; justify-content: space-between; align-items: center; padding: 10px; background: var(--surface-color); border-radius: 8px; margin-bottom: 8px; border: 1px solid var(--border-color);">
                            <div style="flex: 1;">
                                <div style="font-weight: 600; color: var(--text-color);">
                                    <i class="fas fa-mobile-alt" style="margin-right: 8px;"></i>${device.device_name || 'Unknown Device'}
                                </div>
                                <div style="font-size: 0.8rem; color: var(--text-secondary);">Last seen: ${lastSeen}</div>
                            </div>
                            <button class="btn-danger" style="padding: 6px 12px; font-size: 0.8rem;" onclick="unpairDevice('${device.device_id}')">
                                <i class="fas fa-unlink"></i> Unpair
                            </button>
                        </div>
                    `;
                }).join('');
                listEl.innerHTML = html;
            } else {
                section.style.display = 'none';
                listEl.innerHTML = '';
            }
        } catch (e) {
            console.error('Failed to load paired devices:', e);
            section.style.display = 'none';
        }
    }

    async function unpairDevice(deviceId) {
        if (!confirm('Are you sure you want to unpair this device? The phone will need to pair again before sending tasks.')) {
            return;
        }

        try {
            const response = await apiCall(`/api/mobile/devices/${deviceId}`, {
                method: 'DELETE'
            });
            const data = await response.json();
            
            if (data.success) {
                if (typeof showNotification === 'function') {
                    showNotification('Device unpaired successfully', 'success');
                }
                loadPairedDevices();
            } else {
                if (typeof showNotification === 'function') {
                    showNotification(data.error || 'Failed to unpair device', 'error');
                }
            }
        } catch (e) {
            console.error('Failed to unpair device:', e);
            if (typeof showNotification === 'function') {
                showNotification('Failed to unpair device', 'error');
            }
        }
    }

    // Expose unpairDevice globally
    window.unpairDevice = unpairDevice;

    // Copy companion URL to clipboard
    window.copyCompanionUrl = function() {
        const urlEl = document.getElementById('web-companion-url');
        if (!urlEl) return;
        
        const url = urlEl.dataset.url || urlEl.textContent;
        if (!url || url === 'Loading...' || url === 'Could not determine URL') return;
        
        navigator.clipboard.writeText(url).then(() => {
            if (typeof showNotification === 'function') {
                showNotification('URL copied! Open it on your phone.', 'success');
            }
            // Visual feedback
            const originalText = urlEl.textContent;
            urlEl.textContent = '✓ Copied!';
            setTimeout(() => {
                urlEl.textContent = originalText;
            }, 1500);
        }).catch(() => {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = url;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            if (typeof showNotification === 'function') {
                showNotification('URL copied!', 'success');
            }
        });
    };

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

    function updateInboxIndicator(count) {
        const indicator = getEl('mobile-inbox-indicator');
        const countEl = getEl('mobile-inbox-count');
        
        if (indicator) {
            indicator.style.display = count > 0 ? 'flex' : 'none';
        }
        if (countEl) {
            countEl.textContent = count;
        }
    }

    async function pollInboxOnce() {
        if (pollingInFlight) return;
        
        // Skip polling if page is hidden/minimized to prevent freezing in background
        if (document.hidden) {
            return;
        }
        
        pollingInFlight = true;

        try {
            const data = await fetchJson('/api/mobile/inbox/pending', { cacheTTL: 0 });
            if (!data || !data.success) {
                updateInboxIndicator(0);
                return;
            }

            const pending = data.pending;
            if (!pending || !pending.id) {
                currentPendingSubmissionId = null;
                updateInboxIndicator(0);
                return;
            }

            // Update indicator with task count
            const payload = pending.payload || {};
            const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
            updateInboxIndicator(tasks.length);

            if (currentPendingSubmissionId === pending.id) {
                return;
            }

            currentPendingSubmissionId = pending.id;
            renderInboxList(pending);
            open('mobile-inbox-modal');
        } catch (e) {
            updateInboxIndicator(0);
        } finally {
            pollingInFlight = false;
        }
    }

    async function approveInbox() {
        if (operationInProgress) {
            console.log('[MobileInbox] Operation already in progress, skipping approve');
            return;
        }
        const submissionId = currentPendingSubmissionId;
        if (!submissionId) return;
        
        operationInProgress = true;

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
        } finally {
            operationInProgress = false;
        }
    }

    function toggleSelectAll() {
        const checkboxes = Array.from(document.querySelectorAll('.mobile-inbox-task'));
        const allChecked = checkboxes.every(cb => cb.checked);
        const btn = getEl('mobile-inbox-select-all-btn');
        
        checkboxes.forEach(cb => {
            cb.checked = !allChecked;
        });
        
        if (btn) {
            btn.textContent = allChecked ? 'Select All' : 'Deselect All';
        }
    }

    async function rejectInbox() {
        if (operationInProgress) {
            console.log('[MobileInbox] Operation already in progress, skipping reject');
            return;
        }
        const submissionId = currentPendingSubmissionId;
        if (!submissionId) {
            close('mobile-inbox-modal');
            return;
        }
        
        operationInProgress = true;

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
        } finally {
            operationInProgress = false;
        }
    }

    function startPolling() {
        if (pollingTimer) return;
        // Poll every 10 seconds instead of 2.5 to reduce load and prevent freezing
        pollingTimer = window.setInterval(pollInboxOnce, 10000);
        pollInboxOnce();
    }

    function bindUi() {
        // Mobile inbox indicator click - open the inbox modal
        const inboxIndicator = getEl('mobile-inbox-indicator');
        if (inboxIndicator) {
            inboxIndicator.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                // If there's a pending submission, open the inbox modal
                if (currentPendingSubmissionId) {
                    open('mobile-inbox-modal');
                } else {
                    // Otherwise check for pending and show
                    pollInboxOnce().then(() => {
                        if (currentPendingSubmissionId) {
                            open('mobile-inbox-modal');
                        }
                    });
                }
            });
        }

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

        const inboxSelectAll = getEl('mobile-inbox-select-all-btn');
        if (inboxSelectAll) {
            inboxSelectAll.addEventListener('click', toggleSelectAll);
        }

        startPolling();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindUi);
    } else {
        bindUi();
    }
})();
