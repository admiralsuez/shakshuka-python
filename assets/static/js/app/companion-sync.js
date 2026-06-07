// Companion phone app task sync
let companionSyncInterval = null;
const COMPANION_SYNC_KEY = 'shakshuka_companion_last_sync';
const COMPANION_SYNC_INTERVAL = 2 * 60 * 60 * 1000; // 2 hours (for background auto-sync)
const COMPANION_AUTO_SYNC_KEY = 'companion_auto_sync_enabled';

// Paired-state cache (TTL: 60 s) — avoids a round-trip on every button press
let _pairedStateCache = null; // null = unknown, true/false
let _pairedStateCacheAt = 0;
const PAIRED_CACHE_TTL_MS = 60_000;

// Modal state guard to prevent duplicate modals
let _syncModalOpen = false;

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

// Guards / state for on-demand sync
let _syncCheckInProgress = false;  // prevents concurrent inbox checks
let _syncCheckTimeout = null;  // timeout guard for hanging requests

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
    
    // Set timeout guard (30 seconds max)
    _syncCheckTimeout = setTimeout(() => {
        _syncCheckInProgress = false;
    }, 30000);
    
    try {
        if (isManual && window.showNotification) {
            window.showNotification('Checking for tasks from phone...', 'info');
        }
        
        // First, check if there are already pending tasks waiting to be imported
        const response = await fetch('/api/mobile/inbox/pending', { credentials: 'include' });
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.pending && data.pending.id) {
                const pending = data.pending;
                const payload = pending.payload || {};
                const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
                const notes = Array.isArray(payload.notes) ? payload.notes : [];
                const totalItems = tasks.length + notes.length;
                
                if (totalItems > 0) {
                    if (isManual && window.showNotification) {
                        const label = [];
                        if (tasks.length) label.push(`${tasks.length} task${tasks.length > 1 ? 's' : ''}`);
                        if (notes.length) label.push(`${notes.length} note${notes.length > 1 ? 's' : ''}`);
                        window.showNotification(`Found ${label.join(' and ')} from phone`, 'success');
                    }
                    // Show sync modal with new tasks
                    showCompanionSyncModal(pending);
                    clearTimeout(_syncCheckTimeout);
                    _syncCheckInProgress = false;
                    return;
                }
            }
        }
        
        // No pending tasks, signal the phone to push tasks
        if (isManual) {
            try {
                const syncResp = await fetch('/api/mobile/request-sync', {
                    method: 'POST',
                    credentials: 'include',
                });
                if (syncResp.ok) {
                    if (window.showNotification) {
                        window.showNotification('Sync request sent to phone. Waiting for response...', 'info');
                    }
                } else {
                    if (window.showNotification) {
                        window.showNotification('Failed to request sync from phone', 'error');
                    }
                }
            } catch (e) {
                console.debug('Failed to request sync from phone:', e);
                if (window.showNotification) {
                    window.showNotification('Error requesting sync from phone', 'error');
                }
            }
        }
    } catch (e) {
        if (isManual && window.showNotification) {
            window.showNotification('Error fetching tasks from phone', 'error');
        }
        console.debug('Companion sync check failed:', e);
    } finally {
        clearTimeout(_syncCheckTimeout);
        _syncCheckInProgress = false;
    }
}

function showCompanionSyncModal(pending) {
    // Prevent duplicate modals from appearing
    if (_syncModalOpen) {
        console.debug('Sync modal already open, queueing next check');
        return;
    }
    _syncModalOpen = true;
    
    const submissionId = pending.id;
    const payload = pending.payload || {};
    const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
    const notes = Array.isArray(payload.notes) ? payload.notes : [];
    
    // Use the official mobile-inbox-modal instead of creating a custom one
    // The mobile-inbox.js module handles rendering and interaction
    // Just delegate to it by exposing the pending submission for rendering
    if (typeof window.showMobileInboxModal === 'function') {
        window.showMobileInboxModal(pending);
        _syncModalOpen = false; // Let mobile-inbox.js manage modal state
    } else {
        // Fallback: try to trigger the modal directly
        const modal = document.getElementById('mobile-inbox-modal');
        if (modal) {
            // Store the pending submission for mobile-inbox.js to render
            window._companionPendingSubmission = pending;
            if (typeof window.open === 'function') {
                window.open('mobile-inbox-modal');
            }
        }
        _syncModalOpen = false;
    }
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
                const now = new Date().toISOString();
                const formattedTime = typeof window.TimestampFormatter !== 'undefined'
                    ? window.TimestampFormatter.format(now)
                    : now;
                window.DailyResetLog.addCompanionSync({
                    count: totalImported,
                    deviceName: payload.device_name || 'Phone',
                    timestamp: formattedTime,
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
    if (_syncCheckTimeout) clearTimeout(_syncCheckTimeout);
});
