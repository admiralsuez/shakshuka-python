// Companion phone app task sync
let companionSyncInterval = null;
const COMPANION_SYNC_KEY = 'shakshuka_companion_last_sync';
const COMPANION_SYNC_INTERVAL = 2 * 60 * 60 * 1000; // 2 hours
const COMPANION_AUTO_SYNC_KEY = 'companion_auto_sync_enabled';

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

async function checkCompanionTasksSync() {
    try {
        // Check for pending companion tasks
        const response = await fetch('/api/mobile/inbox', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ pending_only: true })
        });
        if (!response.ok) return;
        
        const data = await response.json();
        if (!data.success || !data.items || data.items.length === 0) return;
        
        // Filter for tasks (type might be indicated in item structure)
        const companionTasks = data.items.filter(item => 
            item.type === 'task' || (!item.type && item.title && item.project !== undefined)
        );
        
        if (companionTasks.length === 0) return;
        
        // Show sync modal with new tasks
        showCompanionSyncModal(companionTasks);
    } catch (e) {
        // Silently ignore sync errors
        console.debug('Companion sync check failed:', e);
    }
}

function showCompanionSyncModal(tasks) {
    // Create or reuse modal
    let modal = document.getElementById('companion-sync-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'companion-sync-modal';
        modal.className = 'modal';
        modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';
        document.body.appendChild(modal);
    }
    
    const selected = new Set();
    
    modal.innerHTML = '';
    const content = document.createElement('div');
    content.className = 'modal-content';
    content.style.cssText = 'background:var(--surface-color);border-radius:12px;padding:2rem;max-width:500px;max-height:80vh;overflow-y:auto;box-shadow:0 10px 40px rgba(0,0,0,0.3);';
    
    // Header
    const header = document.createElement('div');
    header.style.cssText = 'margin-bottom:1.5rem;';;
    const title = document.createElement('h2');
    title.textContent = `New Tasks from Phone (${tasks.length})`;
    title.style.cssText = 'margin:0 0 0.5rem 0;';
    header.appendChild(title);
    const subtitle = document.createElement('p');
    subtitle.textContent = 'Select tasks to import to your desktop';
    subtitle.style.cssText = 'margin:0;color:var(--text-secondary);font-size:0.9rem;';
    header.appendChild(subtitle);
    content.appendChild(header);
    
    // Task list with checkboxes
    const listContainer = document.createElement('div');
    listContainer.style.cssText = 'margin-bottom:1.5rem;max-height:400px;overflow-y:auto;';
    
    tasks.forEach((task, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.style.cssText = 'display:flex;align-items:flex-start;gap:0.75rem;padding:0.75rem;border:1px solid var(--border-color);border-radius:6px;margin-bottom:0.5rem;';
        
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = true;
        checkbox.style.cssText = 'margin-top:0.3rem;cursor:pointer;';
        checkbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                selected.add(index);
            } else {
                selected.delete(index);
            }
        });
        selected.add(index);
        itemDiv.appendChild(checkbox);
        
        const taskInfo = document.createElement('div');
        taskInfo.style.cssText = 'flex:1;';
        
        const taskTitle = document.createElement('div');
        taskTitle.textContent = task.title || 'Untitled Task';
        taskTitle.style.cssText = 'font-weight:500;margin-bottom:0.2rem;';
        taskInfo.appendChild(taskTitle);
        
        if (task.project) {
            const projectSpan = document.createElement('div');
            projectSpan.textContent = task.project;
            projectSpan.style.cssText = 'font-size:0.8rem;color:var(--text-secondary);';
            taskInfo.appendChild(projectSpan);
        }
        
        itemDiv.appendChild(taskInfo);
        listContainer.appendChild(itemDiv);
    });
    content.appendChild(listContainer);
    
    // Buttons
    const buttons = document.createElement('div');
    buttons.style.cssText = 'display:flex;gap:0.75rem;justify-content:flex-end;';
    
    const cancelBtn = document.createElement('button');
    cancelBtn.type = 'button';
    cancelBtn.className = 'btn-secondary';
    cancelBtn.textContent = 'Cancel';
    cancelBtn.style.cssText = 'padding:0.6rem 1.2rem;';
    cancelBtn.addEventListener('click', () => {
        modal.style.display = 'none';
    });
    buttons.appendChild(cancelBtn);
    
    const importBtn = document.createElement('button');
    importBtn.type = 'button';
    importBtn.className = 'btn-primary';
    importBtn.textContent = `Import ${selected.size} Task${selected.size === 1 ? '' : 's'}`;
    importBtn.style.cssText = 'padding:0.6rem 1.2rem;';
    importBtn.addEventListener('click', async () => {
        const selectedTasks = Array.from(selected).map(idx => tasks[idx].id);
        await importCompanionTasks(selectedTasks);
        modal.style.display = 'none';
    });
    buttons.appendChild(importBtn);
    content.appendChild(buttons);
    
    modal.appendChild(content);
    modal.style.display = 'flex';
}

async function importCompanionTasks(taskIds) {
    try {
        const response = await fetch('/api/mobile/inbox/approve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({ selected_task_ids: taskIds, selected_note_ids: [] })
        });
        
        if (response.ok) {
            const result = await response.json();
            if (window.showNotification) {
                window.showNotification(`Imported ${taskIds.length} task${taskIds.length === 1 ? '' : 's'}`, 'success');
            }
            // Refresh tasks if available
            if (typeof refreshTasks === 'function') refreshTasks();
            if (window.AppState && typeof AppState.loadTasks === 'function') AppState.loadTasks();
        }
    } catch (e) {
        console.error('Failed to import companion tasks:', e);
        if (window.showNotification) {
            window.showNotification('Failed to import tasks', 'error');
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
    syncBtn.addEventListener('click', checkCompanionTasksSync);
    
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
    if (companionSyncInterval) {
        clearInterval(companionSyncInterval);
    }
});
