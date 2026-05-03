// Task operation lock to prevent race conditions
let taskOperationLock = false;
const TASK_OPERATION_TIMEOUT = 10000; // 10 seconds

function _safeNotify(message, type) {
    try {
        if (window.Utils && typeof window.Utils.safeShowNotification === 'function') {
            window.Utils.safeShowNotification(message, type || 'info');
            return;
        }
        if (typeof showNotification === 'function') {
            showNotification(message, type || 'info');
        }
    } catch (e) {
        console.error('Notification error:', e);
    }
}

function _isTaskObject(obj) {
    return obj && typeof obj === 'object' && typeof obj.id === 'string' && obj.id.trim().length > 0;
}

async function _apiRequestTask(url, options) {
    if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
        const data = await window.Utils.apiRequestJson(url, options || {}, { expectObject: true, retries: 0 });
        if (!_isTaskObject(data)) {
            const err = new Error('Invalid task payload from server');
            err.data = data;
            err.url = url;
            throw err;
        }
        return data;
    }

    if (typeof apiCall !== 'function') {
        throw new Error('apiCall not available');
    }
    const resp = await apiCall(url, options || {});
    const data = await resp.json().catch(() => null);
    if (!resp.ok) {
        const msg = (data && (data.error || data.message)) ? (data.error || data.message) : `HTTP ${resp.status}`;
        const err = new Error(msg);
        err.status = resp.status;
        err.data = data;
        err.url = url;
        throw err;
    }
    if (!_isTaskObject(data)) {
        const err = new Error('Invalid task payload from server');
        err.data = data;
        err.url = url;
        throw err;
    }
    return data;
}

function acquireTaskOperationLock() {
    if (taskOperationLock) {
        return false;
    }
    taskOperationLock = true;
    
    // Auto-release lock after timeout
    setTimeout(() => {
        if (taskOperationLock) {
            console.warn('Task operation lock timeout, releasing lock');
            taskOperationLock = false;
        }
    }, TASK_OPERATION_TIMEOUT);
    
    return true;
}

function releaseTaskOperationLock() {
    taskOperationLock = false;
}

function isTaskOperationInProgress() {
    return taskOperationLock;
}

async function createTask(taskData, options) {
    options = options || {};
    const bypassDuplicateModal = Boolean(options.bypassDuplicateModal);

    // Check if another task operation is in progress
    if (!acquireTaskOperationLock()) {
        console.warn('Task operation already in progress, skipping create');
        showNotification('Another task operation is in progress, please wait', 'warning');
        return null;
    }
    
    try {
        console.log('Creating task with data:', taskData);
        
        // Validate task data before sending
        if (!taskData.title || taskData.title.trim().length === 0) {
            throw new Error('Task title is required');
        }
        
        const newTask = await _apiRequestTask('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });
        console.log('New task created:', newTask);
            
            console.log('Adding task to AppState...');
            await AppState.addTask(newTask);
            
            console.log('Updating dashboard stats...');
            updateDashboardStats();

            // Keep project filter options in sync with active tasks
            try {
                if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
                    Tasks.updateProjectFilterOptions();
                }
            } catch (e) { /* no-op */ }
            
            console.log('Current page:', AppState.get('currentPage'));
            if (AppState.get('currentPage') === 'tasks') {
                console.log('Rendering tasks...');
                // Switch to 'active' view so user can see the newly created task
                setActiveFilter('active');
                renderTasks('active');
            } else if (AppState.get('currentPage') === 'dashboard') {
                console.log('Rendering recent tasks...');
                renderRecentTasks();
            } else if (AppState.get('currentPage') === 'analytics') {
                // Analytics page doesn't need re-rendering, stats are updated via updateDashboardStats()
            }
            
            console.log('Showing success notification...');
            showNotification('Task created successfully!', 'success');
            console.log('Task creation completed successfully');
            return newTask;
    } catch (error) {
        console.error('Error creating task:', error);

        const status = (error && typeof error.status === 'number') ? error.status : null;
        const message = (error && error.message) ? String(error.message) : '';
        const lowerMsg = message.toLowerCase();
        const isDuplicate = status === 409 || lowerMsg.includes('similar task already exists');

        if (isDuplicate && !bypassDuplicateModal) {
            try {
                if (typeof openDuplicateTaskModal === 'function') {
                    openDuplicateTaskModal(taskData);
                } else {
                    _safeNotify(message || 'A similar task already exists', 'warning');
                }
            } catch (e) {
                _safeNotify(message || 'A similar task already exists', 'warning');
            }
            return null;
        }

        if (lowerMsg.includes('login')) {
            _safeNotify('Please log in to create tasks', 'error');
        } else {
            _safeNotify(message || 'Error creating task', 'error');
        }
        return null;
    } finally {
        releaseTaskOperationLock();
    }
}

async function updateTask(taskId, taskData) {
    // Check if another task operation is in progress
    if (!acquireTaskOperationLock()) {
        console.warn('Task operation already in progress, skipping update');
        showNotification('Another task operation is in progress, please wait', 'warning');
        return null;
    }
    
    try {
        const updatedTask = await _apiRequestTask(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(taskData)
        });
            await AppState.updateTask(taskId, updatedTask);
            
            updateDashboardStats();
            
            // Keep project filter options in sync with active tasks
            try {
                if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
                    Tasks.updateProjectFilterOptions();
                }
            } catch (e) { /* no-op */ }
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
                renderRecentTasks();
            } else if (AppState.get('currentPage') === 'analytics') {
                // Analytics page doesn't need re-rendering, stats are updated via updateDashboardStats()
            }
            
            showNotification('Task updated successfully!', 'success');
            return updatedTask;
    } catch (error) {
        console.error('Error updating task:', error);
        if (error.message && error.message.toLowerCase().includes('login')) {
            _safeNotify('Please log in to update tasks', 'error');
        } else {
            _safeNotify(error.message || 'Error updating task', 'error');
        }
        return null;
    } finally {
        releaseTaskOperationLock();
    }
}

async function deleteTask(taskId) {
    // Check if another task operation is in progress
    if (!acquireTaskOperationLock()) {
        console.warn('Task operation already in progress, skipping delete');
        showNotification('Another task operation is in progress, please wait', 'warning');
        return null;
    }
    
    try {
        const currentPage = (AppState && typeof AppState.get === 'function') ? AppState.get('currentPage') : null;
        const tasksPageEl = document.getElementById('tasks-page');
        const isTasksPageActive = Boolean(tasksPageEl && tasksPageEl.classList && tasksPageEl.classList.contains('active'));
        const headers = {
            'Content-Type': 'application/json',
        };
        if (currentPage === 'tasks' && isTasksPageActive) {
            headers['X-Delete-Source'] = 'tasklist';
        }

        if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
            try {
                await window.Utils.apiRequestJson(`/api/tasks/${taskId}`, { method: 'DELETE', headers }, { expectObject: true, retries: 0 });
            } catch (e) {
                // If task is already gone server-side, we can still safely remove it locally.
                if (!(e && typeof e.status === 'number' && e.status === 404)) {
                    throw e;
                }
            }
        } else {
            const response = await apiCall(`/api/tasks/${taskId}`, { method: 'DELETE', headers });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                // If task is already gone server-side, we can still safely remove it locally.
                if (response.status !== 404) {
                    throw new Error(err.error || 'Failed to delete task');
                }
            }
        }

            await AppState.removeTask(taskId);
            updateDashboardStats();
            
            // Keep project filter options in sync with active tasks
            try {
                if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
                    Tasks.updateProjectFilterOptions();
                }
            } catch (e) { /* no-op */ }
            
            if (AppState.get('currentPage') === 'tasks') {
                // Preserve current filter state after deletion
                const currentFilter = AppState.get('currentFilter') || 'active';
                renderTasks(currentFilter);
            } else if (AppState.get('currentPage') === 'dashboard') {
                renderRecentTasks();
            } else if (AppState.get('currentPage') === 'analytics') {
                // Analytics page doesn't need re-rendering, stats are updated via updateDashboardStats()
            }

            if (currentPage === 'tasks' && isTasksPageActive && typeof window.undoDeleteTask === 'function') {
                showNotification('Task deleted. Click to undo.', 'info', {
                    durationMs: 3000,
                    onClick: () => window.undoDeleteTask(taskId)
                });
            } else {
                showNotification('Task deleted successfully!', 'success');
            }
            return true;
    } catch (error) {
        console.error('Error deleting task:', error);
        if (error.message && error.message.toLowerCase().includes('login')) {
            _safeNotify('Please log in to delete tasks', 'error');
        } else {
            _safeNotify(error.message || 'Error deleting task', 'error');
        }
        return false;
    } finally {
        releaseTaskOperationLock();
    }
}

async function completeTask(taskId) {
    // Check if another task operation is in progress
    if (!acquireTaskOperationLock()) {
        console.warn('Task operation already in progress, skipping complete');
        showNotification('Another task operation is in progress, please wait', 'warning');
        return null;
    }
    
    try {
        const completedTask = await _apiRequestTask(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });
            await AppState.updateTask(taskId, completedTask);
            
            updateDashboardStats();
            
            // Keep project filter options in sync with active tasks
            try {
                if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
                    Tasks.updateProjectFilterOptions();
                }
            } catch (e) { /* no-op */ }
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
                renderRecentTasks();
            } else if (AppState.get('currentPage') === 'analytics') {
                // Analytics page doesn't need re-rendering, stats are updated via updateDashboardStats()
                // But we can add a visual refresh indicator if needed
            }
            
            showNotification('Task completed! 🎉', 'success');
            return completedTask;
    } catch (error) {
        console.error('Error completing task:', error);
        if (error.message && error.message.toLowerCase().includes('login')) {
            _safeNotify('Please log in to complete tasks', 'error');
        } else {
            _safeNotify(error.message || 'Error completing task', 'error');
        }
        return null;
    } finally {
        releaseTaskOperationLock();
    }
}

// Modal Functions
function openTaskModal(taskId = null) {
    // Ensure AppState reflects the current editing context so saves use update instead of create
    if (typeof AppState !== 'undefined' && AppState.set) {
        AppState.set('editingTaskId', taskId);
    }
    editingTaskId = taskId;
    const modal = document.getElementById('task-modal');
    const title = document.getElementById('modal-title');
    
    if (taskId) {
        const tasks = AppState.getTasks();
        const task = tasks.find(t => t.id === taskId);
        if (task) {
            title.textContent = 'Edit Task';
            populateTaskForm(task);
        }
    } else {
        title.textContent = 'Add New Task';
        clearTaskForm();
    }
    
    if (modal) {
    modal.classList.add('active');
        modal.style.display = 'flex';
    }
}

function closeTaskModal() {
    const modal = document.getElementById('task-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    // Clear editing state in both local variable and AppState
    if (typeof AppState !== 'undefined' && AppState.set) {
        AppState.set('editingTaskId', null);
    }
    editingTaskId = null;
    clearTaskForm();
}

function openQuickAddModal() {
    const modal = document.getElementById('quick-add-modal');
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex';
    document.getElementById('quick-task-title').focus();
    }
}

function closeQuickAddModal() {
    console.log('closeQuickAddModal called');
    const modal = document.getElementById('quick-add-modal');
    console.log('Modal element:', modal);
    if (modal) {
        // Try both methods to ensure the modal closes
        modal.classList.remove('active');
        modal.style.display = 'none';
        console.log('Modal closed successfully');
    } else {
        console.error('Modal element not found');
    }
    // Reset the form
    const form = document.getElementById('quick-task-form');
    if (form) {
        form.reset();
    }
}

let _pendingDuplicateTaskData = null;

function _findExistingDuplicateTask(taskData) {
    try {
        const title = (taskData && taskData.title ? String(taskData.title) : '').trim().toLowerCase();
        const project = (taskData && taskData.project ? String(taskData.project) : '').trim().toLowerCase();
        if (!title) {
            return null;
        }

        let tasks = [];
        try {
            if (typeof AppState !== 'undefined' && typeof AppState.getTasks === 'function') {
                tasks = AppState.getTasks() || [];
            } else if (AppState && AppState.get) {
                tasks = AppState.get('tasks') || [];
            }
        } catch (e) {
            tasks = [];
        }

        if (!Array.isArray(tasks) || !tasks.length) {
            return null;
        }

        return tasks.find(t => {
            if (!t || !t.title) return false;
            const tTitle = String(t.title).trim().toLowerCase();
            const tProject = (t.project ? String(t.project) : '').trim().toLowerCase();
            const isCompleted = Boolean(t.completed);
            if (isCompleted) return false;
            return tTitle === title && tProject === project;
        }) || null;
    } catch (e) {
        return null;
    }
}

function openDuplicateTaskModal(taskData) {
    const modal = document.getElementById('duplicate-task-modal');
    if (!modal) {
        _safeNotify('A similar task already exists', 'warning');
        return;
    }

    _pendingDuplicateTaskData = Object.assign({}, taskData || {});

    const titleInput = document.getElementById('duplicate-task-new-title');
    const previewEl = document.getElementById('duplicate-task-existing-preview');

    const originalTitle = (_pendingDuplicateTaskData.title || '').trim();
    if (titleInput) {
        titleInput.value = originalTitle;
        // Select the whole title so user can quickly overwrite
        try {
            titleInput.focus();
            titleInput.setSelectionRange(0, titleInput.value.length);
        } catch (e) { /* no-op */ }
    }

    if (previewEl) {
        const existing = _findExistingDuplicateTask(_pendingDuplicateTaskData);
        if (existing) {
            const project = existing.project ? String(existing.project) : '';
            previewEl.textContent = project ? `${existing.title}  b7 ${project}` : existing.title;
        } else {
            const project = _pendingDuplicateTaskData.project ? String(_pendingDuplicateTaskData.project) : '';
            previewEl.textContent = project ? `${originalTitle}  b7 ${project}` : originalTitle;
        }
    }

    modal.style.display = 'flex';
    modal.classList.add('active');
}

function closeDuplicateTaskModal() {
    const modal = document.getElementById('duplicate-task-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    _pendingDuplicateTaskData = null;
}

async function handleDuplicateAddAgainClick() {
    if (!_pendingDuplicateTaskData) {
        closeDuplicateTaskModal();
        return;
    }
    const payload = Object.assign({}, _pendingDuplicateTaskData, { ignore_duplicate: true });
    closeDuplicateTaskModal();
    await createTask(payload, { bypassDuplicateModal: true });
}

async function handleDuplicateRenameAddClick() {
    if (!_pendingDuplicateTaskData) {
        closeDuplicateTaskModal();
        return;
    }
    const input = document.getElementById('duplicate-task-new-title');
    const newTitle = input && typeof input.value === 'string' ? input.value.trim() : '';
    if (!newTitle) {
        _safeNotify('Please enter a new title', 'error');
        if (input) {
            try { input.focus(); } catch (e) { /* no-op */ }
        }
        return;
    }

    const payload = Object.assign({}, _pendingDuplicateTaskData, { title: newTitle });
    closeDuplicateTaskModal();
    await createTask(payload, { bypassDuplicateModal: false });
}

(function initDuplicateTaskModalHandlers() {
    function setup() {
        const modal = document.getElementById('duplicate-task-modal');
        if (!modal) return;

        const cancelHeader = document.getElementById('duplicate-task-cancel');
        const cancelFooter = document.getElementById('duplicate-task-cancel-footer');
        const addAgainBtn = document.getElementById('duplicate-task-add-again');
        const renameAddBtn = document.getElementById('duplicate-task-rename-add');

        if (cancelHeader) {
            cancelHeader.addEventListener('click', closeDuplicateTaskModal);
        }
        if (cancelFooter) {
            cancelFooter.addEventListener('click', closeDuplicateTaskModal);
        }
        if (addAgainBtn) {
            addAgainBtn.addEventListener('click', handleDuplicateAddAgainClick);
        }
        if (renameAddBtn) {
            renameAddBtn.addEventListener('click', handleDuplicateRenameAddClick);
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();

// Expose/augment Tasks object with modal helpers without overwriting the module from tasks.js
window.Tasks = window.Tasks || {};
Object.assign(window.Tasks, {
    openTaskModal,
    openQuickAddModal,
    openScheduleModal: function(...args) {
        if (typeof window.openScheduleModal === 'function') {
            return window.openScheduleModal(...args);
        }
    },
    closeTaskModal,
    closeQuickAddModal,
    closeScheduleModal: function(...args) {
        if (typeof window.closeScheduleModal === 'function') {
            return window.closeScheduleModal(...args);
        }
    }
});

function editTask(taskId) {
    openTaskModal(taskId);
}

async function undoCompleteTask(taskId) {
    await updateTask(taskId, { completed: false, completed_at: null });
    // updateTask already triggers filter refresh via updateDashboardStats path,
    // but make sure project filter reflects newly active tasks even if caller
    // doesn't stay on the tasks page.
    try {
        if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
            Tasks.updateProjectFilterOptions();
        }
    } catch (e) { /* no-op */ }
}

// ── Subtasks Modal ──
function openSubtasksModal(taskId) {
    if (!taskId) return;
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    let modal = document.getElementById('subtasks-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'subtasks-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width:550px;">
                <div class="modal-header">
                    <h2 id="subtasks-modal-title">Subtasks</h2>
                    <button class="modal-close" type="button" id="subtasks-modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div id="subtasks-list" style="display:flex;flex-direction:column;gap:0.4rem;max-height:50vh;overflow-y:auto;"></div>
                    <div style="display:flex;gap:0.5rem;margin-top:0.75rem;">
                        <input type="text" id="subtask-new-input" class="form-input" placeholder="Add subtask..." style="flex:1;padding:0.5rem 0.8rem;">
                        <button type="button" id="subtask-add-btn" class="btn-primary" style="padding:0.5rem 1rem;">Add</button>
                    </div>
                </div>
            </div>`;
        document.body.appendChild(modal);
        document.getElementById('subtasks-modal-close').addEventListener('click', closeSubtasksModal);
        modal.addEventListener('click', (e) => { if (e.target === modal) closeSubtasksModal(); });
        document.getElementById('subtask-add-btn').addEventListener('click', () => addSubtaskFromInput(taskId));
        document.getElementById('subtask-new-input').addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); addSubtaskFromInput(taskId); }
        });
    }

    document.getElementById('subtasks-modal-title').textContent = 'Subtasks: ' + (task.title || 'Untitled');
    // Re-bind the add button for the current task
    const addBtn = document.getElementById('subtask-add-btn');
    const newAddBtn = addBtn.cloneNode(true);
    addBtn.parentNode.replaceChild(newAddBtn, addBtn);
    newAddBtn.addEventListener('click', () => addSubtaskFromInput(taskId));
    const inputEl = document.getElementById('subtask-new-input');
    const newInput = inputEl.cloneNode(true);
    inputEl.parentNode.replaceChild(newInput, inputEl);
    newInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') { e.preventDefault(); addSubtaskFromInput(taskId); }
    });

    renderSubtasksList(taskId);
    modal.style.display = 'flex'; modal.classList.add('active');
    newInput.value = ''; newInput.focus();
}

function closeSubtasksModal() {
    const modal = document.getElementById('subtasks-modal');
    if (modal) { modal.classList.remove('active'); modal.style.display = 'none'; }
}

function renderSubtasksList(taskId) {
    const listEl = document.getElementById('subtasks-list');
    if (!listEl) return;
    listEl.innerHTML = '';
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    const subtasks = Array.isArray(task.subtasks) ? task.subtasks : [];
    if (!subtasks.length) {
        listEl.innerHTML = '<div style="color:var(--text-secondary);font-size:0.85rem;padding:0.5rem;">No subtasks yet</div>';
        return;
    }
    subtasks.forEach((st, idx) => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex;align-items:center;gap:0.5rem;padding:0.35rem 0.5rem;border-radius:6px;border:1px solid var(--border-color);';
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.checked = !!st.done;
        cb.style.cssText = 'width:18px;height:18px;accent-color:var(--accent-color);cursor:pointer;flex-shrink:0;';
        cb.addEventListener('change', () => toggleSubtask(taskId, idx));
        const label = document.createElement('span');
        label.textContent = st.title || '';
        label.style.cssText = 'flex:1;' + (st.done ? 'text-decoration:line-through;opacity:0.6;' : '');
        const delBtn = document.createElement('button');
        delBtn.type = 'button';
        delBtn.textContent = '\u00d7';
        delBtn.style.cssText = 'background:none;border:none;color:#dc3545;font-size:1.1rem;cursor:pointer;padding:0 0.3rem;';
        delBtn.addEventListener('click', () => removeSubtask(taskId, idx));
        row.appendChild(cb); row.appendChild(label); row.appendChild(delBtn);
        listEl.appendChild(row);
    });
}

async function addSubtaskFromInput(taskId) {
    const input = document.getElementById('subtask-new-input');
    const title = (input && input.value || '').trim();
    if (!title) return;
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    const subtasks = Array.isArray(task.subtasks) ? [...task.subtasks] : [];
    subtasks.push({ id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), title, done: false });
    await updateTask(taskId, { subtasks });
    if (input) { input.value = ''; input.focus(); }
    renderSubtasksList(taskId);
}

async function toggleSubtask(taskId, idx) {
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    const subtasks = Array.isArray(task.subtasks) ? [...task.subtasks] : [];
    if (idx >= 0 && idx < subtasks.length) {
        subtasks[idx] = { ...subtasks[idx], done: !subtasks[idx].done };
        await updateTask(taskId, { subtasks });
        renderSubtasksList(taskId);
    }
}

async function removeSubtask(taskId, idx) {
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;
    const subtasks = Array.isArray(task.subtasks) ? [...task.subtasks] : [];
    if (idx >= 0 && idx < subtasks.length) {
        subtasks.splice(idx, 1);
        await updateTask(taskId, { subtasks });
        renderSubtasksList(taskId);
    }
}

// Expose subtasks modal
window.openSubtasksModal = openSubtasksModal;

// ── Undo toast for strike actions ──
let _pendingStrikeUndo = null;

function strikeTaskWithUndo(taskId, strikeAction) {
    // strikeAction is a function that performs the actual API call
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    const taskTitle = task.title || 'Untitled';
    _pendingStrikeUndo = { taskId, timer: null };

    _pendingStrikeUndo.timer = setTimeout(() => {
        _pendingStrikeUndo = null;
        strikeAction();
    }, 5000);

    if (window.showNotification) {
        window.showNotification(`"${taskTitle}" will be struck. Click to undo.`, 'info', {
            durationMs: 5000,
            onClick: () => {
                if (_pendingStrikeUndo && _pendingStrikeUndo.taskId === taskId) {
                    clearTimeout(_pendingStrikeUndo.timer);
                    _pendingStrikeUndo = null;
                    if (window.showNotification) window.showNotification('Strike cancelled', 'success');
                }
            }
        });
    }
}
window.strikeTaskWithUndo = strikeTaskWithUndo;

// ── Snooze UI ──
function openSnoozeMenu(taskId, anchorEl) {
    if (!taskId) return;
    // Remove existing snooze menu
    const existing = document.getElementById('snooze-popup-menu');
    if (existing) existing.remove();

    const menu = document.createElement('div');
    menu.id = 'snooze-popup-menu';
    menu.style.cssText = 'position:fixed;z-index:5000;background:var(--surface-color);border:1px solid var(--border-color);border-radius:10px;padding:6px;box-shadow:0 8px 20px var(--shadow-color);display:flex;flex-direction:column;gap:2px;min-width:140px;';

    const options = [
        { label: 'Tomorrow', days: 1 },
        { label: 'In 3 days', days: 3 },
        { label: 'Next week', days: 7 },
        { label: 'In 2 weeks', days: 14 },
    ];

    options.forEach(opt => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.textContent = opt.label;
        btn.style.cssText = 'border:none;background:transparent;padding:5px 10px;border-radius:6px;font-size:0.8rem;text-align:left;cursor:pointer;color:var(--text-secondary);';
        btn.addEventListener('mouseenter', () => { btn.style.background = 'var(--border-color)'; btn.style.color = 'var(--text-color)'; });
        btn.addEventListener('mouseleave', () => { btn.style.background = 'transparent'; btn.style.color = 'var(--text-secondary)'; });
        btn.addEventListener('click', async () => {
            menu.remove();
            const now = new Date();
            const target = new Date(now.getFullYear(), now.getMonth(), now.getDate() + opt.days);
            const yyyy = target.getFullYear();
            const mm = String(target.getMonth() + 1).padStart(2, '0');
            const dd = String(target.getDate()).padStart(2, '0');
            const snoozedUntil = `${yyyy}-${mm}-${dd}`;
            await updateTask(taskId, { snoozed_until: snoozedUntil });
            _safeNotify(`Task snoozed until ${snoozedUntil}`, 'success');
        });
        menu.appendChild(btn);
    });

    document.body.appendChild(menu);
    // Position near anchor
    if (anchorEl) {
        const rect = anchorEl.getBoundingClientRect();
        menu.style.top = (rect.bottom + 4) + 'px';
        menu.style.left = rect.left + 'px';
    } else {
        menu.style.top = '50%'; menu.style.left = '50%';
    }
    // Close on outside click
    const closeHandler = (e) => {
        if (!menu.contains(e.target)) { menu.remove(); document.removeEventListener('click', closeHandler); }
    };
    setTimeout(() => document.addEventListener('click', closeHandler), 0);
}
window.openSnoozeMenu = openSnoozeMenu;

// Form Submissions
async function saveTask() {
    // Prevent duplicate task creation
    if (window.taskCreationInProgress) {
        console.log('Task creation already in progress, skipping duplicate call');
        return;
    }
    
    window.taskCreationInProgress = true;
    
    try {
    const form = document.getElementById('task-form');
    const formData = new FormData(form);
    
    const dueRaw = document.getElementById('task-due-date').value;
    const ownerEl = document.getElementById('task-owner');
    const taskData = {
        title: document.getElementById('task-title').value,
        description: document.getElementById('task-description').value,
        project: document.getElementById('task-project').value,
        owner: ownerEl ? ownerEl.value : '',
        estimated_duration: parseInt(document.getElementById('task-duration').value)
    };
    // Only include due_date if provided; backend rejects empty strings
    if (dueRaw && dueRaw.trim().length > 0) {
        taskData.due_date = dueRaw.trim();
    }

    if (!taskData.title.trim()) {
        showNotification('Please enter a task title', 'error');
        return;
    }

        const editingTaskId = AppState.get('editingTaskId');
        if (editingTaskId) {
            await updateTask(editingTaskId, taskData);
            closeTaskModal();
        } else {
            const created = await createTask(taskData);
            // Only close the modal on successful creation or when a task was
            // actually created. If a duplicate was detected, createTask will
            // return null and open the duplicate-task modal instead.
            if (created) {
                closeTaskModal();
            }
        }
        
    } catch (error) {
        console.error('Error saving task:', error);
    } finally {
        // Always reset the flag, even if an error occurs
        window.taskCreationInProgress = false;
    }
}
