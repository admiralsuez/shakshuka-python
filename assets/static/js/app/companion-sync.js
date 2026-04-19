// Companion phone app task sync
let companionSyncInterval = null;
const COMPANION_SYNC_KEY = 'shakshuka_companion_last_sync';
const COMPANION_SYNC_INTERVAL = 2 * 60 * 60 * 1000; // 2 hours
const COMPANION_AUTO_SYNC_KEY = 'companion_auto_sync_enabled';

// Paired-state cache (TTL: 60 s) — avoids a round-trip on every button press
let _pairedStateCache = null; // null = unknown, true/false
let _pairedStateCacheAt = 0;
const PAIRED_CACHE_TTL_MS = 60_000;

async function _isPhonePaired() {
    if (_pairedStateCache !== null && (Date.now() - _pairedStateCacheAt) < PAIRED_CACHE_TTL_MS) {
        return _pairedStateCache;
    }
    try {
        const resp = await fetch('/api/mobile/devices', { credentials: 'include' });
        if (resp.ok) {
            const data = await resp.json();
            _pairedStateCache = !!(data.success && Array.isArray(data.devices) && data.devices.length > 0);
        } else {
            _pairedStateCache = false;
        }
    } catch (e) {
        _pairedStateCache = false;
    }
    _pairedStateCacheAt = Date.now();
    return _pairedStateCache;
}

function _openPairModal() {
    if (typeof window.openPairPhoneModal === 'function') {
        window.openPairPhoneModal();
    } else {
        // Fallback: click the header pair button if the function isn't ready yet
        const btn = document.getElementById('pair-phone-btn');
        if (btn) btn.click();
    }
}

// Guards / polling state
let _syncCheckInProgress = false;  // prevents concurrent inbox checks
let _syncRequestPollInterval = null;
let _syncRequestPollCount = 0;
const SYNC_POLL_INTERVAL_MS = 5000; // poll every 5 s after requesting sync
const SYNC_POLL_MAX_TICKS = 18;     // give up after 90 s

function _stopSyncRequestPoll() {
    if (_syncRequestPollInterval) {
        clearInterval(_syncRequestPollInterval);
        _syncRequestPollInterval = null;
    }
    _syncRequestPollCount = 0;
}

async function _syncRequestPollTick() {
    _syncRequestPollCount++;
    if (_syncRequestPollCount > SYNC_POLL_MAX_TICKS) {
        _stopSyncRequestPoll();
        return;
    }
    try {
        const resp = await fetch('/api/mobile/inbox/pending', { credentials: 'include' });
        if (!resp.ok) return;
        const data = await resp.json();
        if (!data.success || !data.pending || !data.pending.id) return;
        const pl = data.pending.payload || {};
        const total = (Array.isArray(pl.tasks) ? pl.tasks.length : 0)
                    + (Array.isArray(pl.notes) ? pl.notes.length : 0);
        if (total > 0) {
            _stopSyncRequestPoll();
            showCompanionSyncModal(data.pending);
        }
    } catch (e) {
        console.debug('Sync request poll error:', e);
    }
}

function _startSyncRequestPoll() {
    _stopSyncRequestPoll();
    _syncRequestPollInterval = setInterval(_syncRequestPollTick, SYNC_POLL_INTERVAL_MS);
}

function isCompanionAutoSyncEnabled() {
    // Default to true if not set
    const stored = localStorage.getItem(COMPANION_AUTO_SYNC_KEY);
    return stored === null || stored === 'true';
}

function initializeCompanionSync() {
    // Only auto-sync if enabled in settings
    if (!isCompanionAutoSyncEnabled()) return;
    
    // Sync on startup
    checkCompanionTasksSync();
    
    // Auto-sync every 2 hours
    if (companionSyncInterval) clearInterval(companionSyncInterval);
    companionSyncInterval = setInterval(() => {
        checkCompanionTasksSync();
    }, COMPANION_SYNC_INTERVAL);
}

function updateCompanionAutoSync() {
    const toggle = document.getElementById('companion-auto-sync-toggle');
    if (!toggle) return;
    
    const isEnabled = toggle.checked;
    localStorage.setItem(COMPANION_AUTO_SYNC_KEY, isEnabled);
    
    if (isEnabled) {
        // Start auto-sync
        initializeCompanionSync();
    } else {
        // Stop auto-sync
        if (companionSyncInterval) {
            clearInterval(companionSyncInterval);
            companionSyncInterval = null;
        }
    }
}

async function checkCompanionTasksSync(isManual = false) {
    if (_syncCheckInProgress) return;
    _syncCheckInProgress = true;
    // A manual press cancels any outstanding background poll before re-checking
    if (isManual) _stopSyncRequestPoll();
    try {
        if (isManual && window.showNotification) {
            window.showNotification('Checking for tasks from phone...', 'info');
        }
        
        const response = await fetch('/api/mobile/inbox/pending', { credentials: 'include' });
        if (!response.ok) {
            if (isManual && window.showNotification) {
                window.showNotification('Error fetching tasks from phone', 'error');
            }
            return;
        }
        
        const data = await response.json();
        if (!data.success || !data.pending || !data.pending.id) {
            if (isManual) {
                // Signal the phone to push tasks, then auto-poll for the response
                try {
                    await fetch('/api/mobile/request-sync', {
                        method: 'POST',
                        credentials: 'include',
                    });
                } catch (e) {
                    console.debug('Failed to request sync from phone:', e);
                }
                _startSyncRequestPoll();
                if (window.showNotification) {
                    window.showNotification('Waiting for phone to push tasks \u2014 the import dialog will appear automatically.', 'info');
                }
            }
            return;
        }
        
        const pending = data.pending;
        const payload = pending.payload || {};
        const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
        const notes = Array.isArray(payload.notes) ? payload.notes : [];
        const totalItems = tasks.length + notes.length;
        
        if (totalItems === 0) {
            if (isManual && window.showNotification) {
                window.showNotification('No new tasks from phone', 'info');
            }
            return;
        }
        
        if (isManual && window.showNotification) {
            const label = [];
            if (tasks.length) label.push(`${tasks.length} task${tasks.length > 1 ? 's' : ''}`);
            if (notes.length) label.push(`${notes.length} note${notes.length > 1 ? 's' : ''}`);
            window.showNotification(`Found ${label.join(' and ')} from phone`, 'success');
        }
        
        // Show sync modal with new tasks
        showCompanionSyncModal(pending);
    } catch (e) {
        if (isManual && window.showNotification) {
            window.showNotification('Error fetching tasks from phone', 'error');
        }
        console.debug('Companion sync check failed:', e);
    } finally {
        _syncCheckInProgress = false;
    }
}

function showCompanionSyncModal(pending) {
    _stopSyncRequestPoll(); // tasks arrived — no need to keep polling
    const submissionId = pending.id;
    const payload = pending.payload || {};
    const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
    const notes = Array.isArray(payload.notes) ? payload.notes : [];
    const deviceName = pending.device_name || payload.device_name || 'Phone';
    const totalItems = tasks.length + notes.length;
    
    // Create or reuse modal
    let modal = document.getElementById('companion-sync-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'companion-sync-modal';
        modal.className = 'modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';
        document.body.appendChild(modal);
    }
    
    const selectedTaskIds = new Set();
    const selectedNoteIds = new Set();
    
    modal.innerHTML = '';
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.cssText = 'background:var(--surface-color);border-radius:12px;padding:2rem;max-width:500px;width:90%;max-height:80vh;overflow-y:auto;box-shadow:0 10px 40px rgba(0,0,0,0.3);';
    
    // Header
    const header = document.createElement('div');
    header.style.cssText = 'margin-bottom:1.5rem;';
    const title = document.createElement('h2');
    title.textContent = `New from ${deviceName}`;
    title.style.cssText = 'margin:0 0 0.5rem 0;';
    header.appendChild(title);
    const subtitle = document.createElement('p');
    const itemLabels = [];
    if (tasks.length) itemLabels.push(`${tasks.length} task${tasks.length > 1 ? 's' : ''}`);
    if (notes.length) itemLabels.push(`${notes.length} note${notes.length > 1 ? 's' : ''}`);
    subtitle.textContent = `Select ${itemLabels.join(' and ')} to import`;
    subtitle.style.cssText = 'margin:0;color:var(--text-secondary);font-size:0.9rem;';
    header.appendChild(subtitle);
    content.appendChild(header);
    
    // Item list with checkboxes
    const listContainer = document.createElement('div');
    listContainer.style.cssText = 'margin-bottom:1.5rem;max-height:400px;overflow-y:auto;display:flex;flex-direction:column;gap:0.5rem;';
    
    tasks.forEach(task => {
        const id = String(task.client_task_id || task.id || '').trim();
        if (!id) return;
        selectedTaskIds.add(id);
        
        const label = document.createElement('label');
        label.style.cssText = 'display:flex;align-items:flex-start;gap:0.75rem;padding:0.75rem;border:1px solid var(--border-color);border-radius:6px;cursor:pointer;';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = true;
        checkbox.style.cssText = 'margin-top:0.3rem;cursor:pointer;flex-shrink:0;';
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) selectedTaskIds.add(id); else selectedTaskIds.delete(id);
            updateImportBtn();
        });
        label.appendChild(checkbox);
        
        const info = document.createElement('div');
        const taskTitle = document.createElement('div');
        taskTitle.textContent = task.title || task.name || 'Untitled Task';
        taskTitle.style.cssText = 'font-weight:500;';
        info.appendChild(taskTitle);
        if (task.project) {
            const meta = document.createElement('div');
            meta.textContent = task.project;
            meta.style.cssText = 'font-size:0.8rem;color:var(--text-secondary);';
            info.appendChild(meta);
        }
        label.appendChild(info);
        listContainer.appendChild(label);
    });
    
    notes.forEach(note => {
        const id = String(note.client_note_id || note.id || '').trim();
        if (!id) return;
        selectedNoteIds.add(id);
        
        const label = document.createElement('label');
        label.style.cssText = 'display:flex;align-items:flex-start;gap:0.75rem;padding:0.75rem;border:1px solid var(--border-color);border-radius:6px;cursor:pointer;';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = true;
        checkbox.style.cssText = 'margin-top:0.3rem;cursor:pointer;flex-shrink:0;';
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) selectedNoteIds.add(id); else selectedNoteIds.delete(id);
            updateImportBtn();
        });
        label.appendChild(checkbox);
        
        const info = document.createElement('div');
        const noteTitle = document.createElement('div');
        noteTitle.textContent = (note.title || 'Untitled Note') + ' (note)';
        noteTitle.style.cssText = 'font-weight:500;';
        info.appendChild(noteTitle);
        label.appendChild(info);
        listContainer.appendChild(label);
    });
    content.appendChild(listContainer);
    
    // Buttons
    const buttons = document.createElement('div');
    buttons.style.cssText = 'display:flex;gap:0.75rem;justify-content:flex-end;';
    
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn-secondary';
    cancelBtn.textContent = 'Skip';
    cancelBtn.addEventListener('click', async () => {
        modal.style.display = 'none';
        // Reject the submission so it doesn't block newer submissions from appearing
        try {
            await fetch(`/api/mobile/inbox/${submissionId}/reject`, {
                method: 'POST',
                credentials: 'include',
            });
        } catch (e) {
            console.debug('Failed to reject skipped submission:', e);
        }
        // Check if there are more pending submissions
        setTimeout(() => checkCompanionTasksSync(false), 300);
    });
    buttons.appendChild(cancelBtn);
    
    const importBtn = document.createElement('button');
    importBtn.type = 'button';
    importBtn.className = 'btn-primary';
    importBtn.style.cssText = 'padding:0.6rem 1.2rem;';
    
    function updateImportBtn() {
        const count = selectedTaskIds.size + selectedNoteIds.size;
        importBtn.textContent = `Import ${count} item${count === 1 ? '' : 's'}`;
        importBtn.disabled = count === 0;
    }
    updateImportBtn();
    
    importBtn.addEventListener('click', async () => {
        await importCompanionTasks(submissionId, Array.from(selectedTaskIds), Array.from(selectedNoteIds), payload);
        modal.style.display = 'none';
    });
    buttons.appendChild(importBtn);
    content.appendChild(buttons);
    
    modal.appendChild(content);
    modal.style.display = 'flex';
}

async function importCompanionTasks(submissionId, taskIds, noteIds, pendingPayload) {
    try {
        const response = await fetch(`/api/mobile/inbox/${submissionId}/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ selected_task_ids: taskIds, selected_note_ids: noteIds || [] })
        });
        
        if (response.ok) {
            const result = await response.json();
            const totalImported = (result.created_tasks || 0) + (result.created_notes || 0);
            if (window.showNotification) {
                window.showNotification(`Imported ${totalImported} item${totalImported === 1 ? '' : 's'} from phone`, 'success');
            }
            // Record in the notifications modal
            if (window.DailyResetLog && typeof window.DailyResetLog.addCompanionSync === 'function') {
                const payload = pendingPayload || {};
                const importedTasks = (Array.isArray(payload.tasks) ? payload.tasks : [])
                    .filter(t => taskIds.includes(String(t.client_task_id || t.id || '')));
                window.DailyResetLog.addCompanionSync({
                    count: totalImported,
                    deviceName: payload.device_name || 'Phone',
                    timestamp: new Date().toLocaleTimeString(),
                    tasks: importedTasks,
                });
            }
            // Refresh tasks if available
            if (typeof refreshTasks === 'function') refreshTasks();
            if (window.AppState && typeof AppState.loadTasks === 'function') AppState.loadTasks();
            
            // Check for more pending submissions after a short delay
            setTimeout(() => checkCompanionTasksSync(false), 500);
        } else {
            if (window.showNotification) {
                window.showNotification('Failed to import from phone', 'error');
            }
        }
    } catch (e) {
        console.error('Failed to import companion tasks:', e);
        if (window.showNotification) {
            window.showNotification('Failed to import from phone', 'error');
        }
    }
}

// Add sync button to tasks page header
function addCompanionSyncButton() {
    // Only add to My Tasks page, not other task pages
    const tasksPage = document.getElementById('tasks-page');
    if (!tasksPage || !tasksPage.classList.contains('active')) return;
    
    const pageHeader = tasksPage.querySelector('.page-header');
    if (!pageHeader) return;
    
    // Check if button already exists
    if (document.getElementById('companion-sync-btn')) return;
    
    const syncBtn = document.createElement('button');
    syncBtn.id = 'companion-sync-btn';
    syncBtn.type = 'button';
    syncBtn.className = 'pair-phone-cta';
    syncBtn.innerHTML = '<i class="fas fa-mobile-alt"></i>Sync';
    syncBtn.title = 'Check for tasks from companion phone app';
    syncBtn.addEventListener('click', async () => {
        const paired = await _isPhonePaired();
        if (!paired) {
            _openPairModal();
            return;
        }
        checkCompanionTasksSync(true);
    });
    
    // Insert in header-actions (where other action buttons are)
    const headerActions = pageHeader.querySelector('.header-actions');
    if (headerActions) {
        headerActions.insertBefore(syncBtn, headerActions.firstChild);
    } else {
        pageHeader.appendChild(syncBtn);
    }
}

// Initialize when app loads
if (typeof window !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            // Load saved auto-sync setting
            const autoSyncToggle = document.getElementById('companion-auto-sync-toggle');
            if (autoSyncToggle) {
                autoSyncToggle.checked = isCompanionAutoSyncEnabled();
            }
            
            initializeCompanionSync();
            addCompanionSyncButton();
        }, 500);
    });
    
    // Re-add button when tasks page is shown
    const origShowPage = window.showPage;
    if (typeof origShowPage === 'function') {
        window.showPage = function(pageName) {
            const result = origShowPage.call(this, pageName);
            if (pageName === 'tasks') {
                setTimeout(addCompanionSyncButton, 100);
            }
            return result;
        };
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    if (companionSyncInterval) clearInterval(companionSyncInterval);
    _stopSyncRequestPoll();
});
