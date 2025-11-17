// Tasks Module

// Task management functions
async function loadTasks() {
    try {
        const response = await apiCall('/api/tasks');
        const baseTasks = await response.json();

        let merged = Array.isArray(baseTasks) ? baseTasks : [];

        // Merge scheduled tasks from Planner v2 so Tasks page shows them too
        try {
            const schedResp = await apiCall('/api/planner-v2/schedule');
            const schedData = await schedResp.json();
            if (schedData && schedData.success && schedData.scheduled_tasks) {
                const flatScheduled = [];
                Object.values(schedData.scheduled_tasks).forEach(dayMap => {
                    Object.values(dayMap).forEach(hourTasks => {
                        hourTasks.forEach(t => flatScheduled.push(t));
                    });
                });
                // Merge schedule fields into base tasks WITHOUT overwriting strike/completion flags
                const byId = new Map();
                merged.forEach(t => byId.set(t.id, { ...t }));
                flatScheduled.forEach(st => {
                    const base = byId.get(st.id) || {};
                    const mergedTask = { ...base };
                    // Only take scheduling-related fields from planner payload
                    mergedTask.scheduled_hour = st.scheduled_hour ?? base.scheduled_hour;
                    mergedTask.scheduled_minute = st.scheduled_minute ?? base.scheduled_minute;
                    mergedTask.scheduled_date = st.scheduled_date ?? base.scheduled_date;
                    mergedTask.scheduled_duration = st.scheduled_duration ?? base.scheduled_duration;
                    // IMPORTANT: Trust base strike/completion flags (Tasks API) after resets
                    mergedTask.completed = Boolean(base.completed) || Boolean(st.completed);
                    mergedTask.struck_today = Boolean(base.struck_today);
                    mergedTask.struck_forever = Boolean(base.struck_forever) || Boolean(st.struck_forever);
                    mergedTask.strike_report = base.strike_report || st.strike_report || '';
                    mergedTask.strike_count = Math.max(Number(base.strike_count || 0), Number(st.strike_count || 0));
                    byId.set(st.id, mergedTask);
                });
                merged = Array.from(byId.values());
            }
        } catch (e) {
            // ignore if planner-v2 endpoint not available
        }

        AppState.setTasks(merged);
        // Update project filter options based on latest tasks
        try {
            if (typeof updateProjectFilterOptions === 'function') {
                updateProjectFilterOptions();
            }
        } catch (e) { /* no-op */ }
        // Preserve current filters when rendering
        const currentFilter = (AppState && AppState.get) ? AppState.get('currentFilter') || 'active' : 'active';
        renderTasks(currentFilter);
        updateTaskStats();
        try { if (typeof updateDashboardStats === 'function') updateDashboardStats(); } catch(e) {}
        Utils.Logger.info(`Loaded ${merged.length} tasks`);
    } catch (error) {
        Utils.Logger.error('Failed to load tasks:', error);
        Utils.safeShowNotification('Failed to load tasks', 'error');
    }
}

async function saveTask() {
    const taskData = getTaskFormData();
    if (!taskData) return;

    try {
        const response = await apiCall('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            closeTaskModal();
            loadTasks();
            // If we're on the planner page, refresh available tasks immediately
            try {
                if (AppState.get && AppState.get('currentPage') === 'planner') {
                    if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.loadAvailableTasks === 'function') {
                        window.DailyPlannerV2.loadAvailableTasks();
                    }
                }
            } catch (e) { /* no-op */ }
            Utils.safeShowNotification('Task saved successfully!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to save task', 'error');
        }
    } catch (error) {
        Logger.error('Failed to save task:', error);
        Utils.safeShowNotification('Failed to save task', 'error');
    }
}

async function saveQuickTask() {
    const quickTaskData = getQuickTaskFormData();
    if (!quickTaskData) return;

    try {
        const response = await apiCall('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(quickTaskData)
        });

        if (response.ok) {
            closeQuickAddModal();
            loadTasks();
            // Refresh available tasks in planner regardless of current page (if planner is initialized)
            try {
                if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.loadAvailableTasks === 'function') {
                    window.DailyPlannerV2.loadAvailableTasks();
                }
            } catch (e) { /* no-op */ }
            Utils.safeShowNotification('Task added successfully!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to add task', 'error');
        }
    } catch (error) {
        Logger.error('Failed to save quick task:', error);
        Utils.safeShowNotification('Failed to add task', 'error');
    }
}

async function updateTask(taskId, taskData) {
    try {
        const response = await apiCall(`/api/tasks/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            loadTasks();
            Utils.safeShowNotification('Task updated successfully!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to update task', 'error');
        }
    } catch (error) {
        Logger.error('Failed to update task:', error);
        Utils.safeShowNotification('Failed to update task', 'error');
    }
}

async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;

    try {
        const response = await apiCall(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Preserve current filter before refreshing
            const currentFilter = (AppState && AppState.get) ? AppState.get('currentFilter') || 'active' : 'active';
            const currentPage = (AppState && AppState.get) ? AppState.get('currentPage') : 'tasks';
            
            // Reload tasks while maintaining filter state
            await loadTasks();
            
            // Re-apply the filter if we're on tasks page
            if (currentPage === 'tasks') {
                try {
                    if (typeof setActiveFilter === 'function') setActiveFilter(currentFilter);
                    if (typeof renderTasks === 'function') renderTasks(currentFilter);
                } catch (e) { /* no-op */ }
            }
            
            try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
            // Immediately reflect deletion in Planner v2 if present
            try {
                if (window.DailyPlannerV2) {
                    if (typeof window.DailyPlannerV2.removeScheduledElementsByTaskId === 'function') {
                        window.DailyPlannerV2.removeScheduledElementsByTaskId(taskId);
                    }
                    if (typeof window.DailyPlannerV2.loadAvailableTasks === 'function') {
                        window.DailyPlannerV2.loadAvailableTasks();
                    }
                    if (typeof window.DailyPlannerV2.loadScheduledTasksFromBackend === 'function') {
                        window.DailyPlannerV2.loadScheduledTasksFromBackend();
                    }
                }
            } catch (e) { /* no-op */ }
            Utils.safeShowNotification('Task deleted successfully!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to delete task', 'error');
        }
    } catch (error) {
        Logger.error('Failed to delete task:', error);
        Utils.safeShowNotification('Failed to delete task', 'error');
    }
}

async function strikeTaskToday(taskId) {
    try {
        const response = await apiCall(`/api/tasks/${taskId}/strike`, {
            method: 'POST',
            body: JSON.stringify({ type: 'today' })
        });

if (response.ok) {
            closeStrikeModal();
            loadTasks();
            try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
            Utils.safeShowNotification('Task marked as completed today!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to strike task', 'error');
        }
    } catch (error) {
        Logger.error('Failed to strike task:', error);
        Utils.safeShowNotification('Failed to strike task', 'error');
    }
}

async function strikeTaskForever(taskId) {
    try {
        const response = await apiCall(`/api/tasks/${taskId}/strike`, {
            method: 'POST',
            body: JSON.stringify({ type: 'forever' })
        });

if (response.ok) {
            closeStrikeModal();
            loadTasks();
            try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
            Utils.safeShowNotification('Task marked as completed forever!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to strike task', 'error');
        }
    } catch (error) {
        Logger.error('Failed to strike task forever:', error);
        Utils.safeShowNotification('Failed to strike task', 'error');
    }
}

// Task form handling
function getTaskFormData() {
    const title = document.getElementById('task-title')?.value.trim();
    const description = document.getElementById('task-description')?.value.trim();
    const priority = document.getElementById('task-priority')?.value || 'medium';
    const project = document.getElementById('task-project')?.value || '';

    if (!title) {
        Utils.safeShowNotification('Please enter a task title', 'error');
        return null;
    }

    return {
        title,
        description,
        priority,
        project
    };
}

function getQuickTaskFormData() {
    const title = document.getElementById('quick-task-title')?.value.trim();

    if (!title) {
        Utils.safeShowNotification('Please enter a task title', 'error');
        return null;
    }

    return {
        title,
        description: '',
        priority: 'medium',
        project: ''
    };
}

function openTaskModal(taskId = null) {
    const modal = document.getElementById('task-modal');
    const form = document.getElementById('task-form');
    const titleInput = document.getElementById('task-title');
    const descriptionInput = document.getElementById('task-description');
    const projectSelect = document.getElementById('task-project');

    if (taskId) {
        // Edit existing task
        const tasks = AppState.getTasks();
        const task = tasks.find(t => t.id === taskId);

        if (task) {
            AppState.set('editingTaskId', taskId);
            titleInput.value = task.title;
            descriptionInput.value = task.description || '';
            projectSelect.value = task.project || '';

            document.getElementById('modal-title').textContent = 'Edit Task';
            document.getElementById('save-task').textContent = 'Update Task';
        }
    } else {
        // New task
        AppState.set('editingTaskId', null);
        form.reset();
        document.getElementById('modal-title').textContent = 'Add New Task';
        document.getElementById('save-task').textContent = 'Add Task';
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
    AppState.set('editingTaskId', null);
}

function openQuickAddModal() {
    const modal = document.getElementById('quick-add-modal');
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex';
        document.getElementById('quick-task-title').value = '';
        document.getElementById('quick-task-title').focus();
    }
}

function closeQuickAddModal() {
    const modal = document.getElementById('quick-add-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
}

// Task rendering
function renderTasks() {
    const tasks = AppState.getTasks();
    const sortedTasks = sortTasksForDisplay(tasks);
    const filter = AppState.get('currentFilter') || 'active';
    const projectFilter = AppState.get('projectFilter') || 'all';
    let filteredTasks = filterTasks(sortedTasks, filter);

    if (projectFilter && projectFilter !== 'all') {
        filteredTasks = filteredTasks.filter(task => {
            const name = (task.project || '').trim();
            if (projectFilter === '__none__') {
                return !name;
            }
            return name === projectFilter;
        });
    }

    const tasksContainer = document.getElementById('tasks-list');
    if (!tasksContainer) return;

    tasksContainer.innerHTML = '';

    if (filteredTasks.length === 0) {
        tasksContainer.innerHTML = `
            <div class="no-tasks">
                <i class="fas fa-clipboard-list"></i>
                <h3>No tasks found</h3>
                <p>Add some tasks to get started!</p>
            </div>
        `;
        return;
    }

    filteredTasks.forEach(task => {
        const taskElement = createTaskElement(task);
        tasksContainer.appendChild(taskElement);
    });

    // Re-attach drag and drop listeners
    setupDragAndDrop();
}

// Sync strike classes with current task state (used after daily reset to remove stale CSS classes)
function syncStrikeClassesFromState() {
    const tasks = AppState.getTasks();
    tasks.forEach(task => {
        const taskEl = document.getElementById(`task-${task.id}`);
        if (taskEl) {
            // Remove old strike classes
            taskEl.classList.remove('struck-today', 'struck-forever');
            
            // Re-apply based on current task state
            if (task.struck_today) taskEl.classList.add('struck-today');
            if (task.completed || task.struck_forever) taskEl.classList.add('struck-forever');
            
            // Update title class
            const titleEl = taskEl.querySelector('.task-title');
            if (titleEl) {
                titleEl.classList.remove('struck');
                if (task.struck_today || task.completed || task.struck_forever) {
                    titleEl.classList.add('struck');
                }
            }
        }
    });
}

// Export to window for external access
window.syncStrikeClassesFromState = syncStrikeClassesFromState;

function createTaskElement(task) {
    const taskDiv = document.createElement('div');
    taskDiv.className = `task-item ${task.status || 'pending'}`;
    taskDiv.id = `task-${task.id}`;
    taskDiv.setAttribute('data-task-id', task.id);
    taskDiv.draggable = true;

    if (task.struck_today) taskDiv.classList.add('struck-today');
    // Treat completed as a persistent strike for styling purposes
    if (task.completed || task.struck_forever) taskDiv.classList.add('struck-forever');

    taskDiv.innerHTML = `
        <div class="task-project-tag">
            <span class="project-tag ${task.project ? '' : 'no-project'}">
                ${task.project || 'No Project'}
            </span>
        </div>

        <div class="task-content">
            <h3 class="task-title ${task.struck_today || task.completed || task.struck_forever ? 'struck' : ''}">
                ${Utils.sanitizeHTML(task.title)}
            </h3>
            ${task.description ? `
                <p class="task-description">
                    ${Utils.sanitizeHTML(task.description)}
                </p>
            ` : ''}
            ${task.strike_report ? `
                <div class="strike-report">
                    ${Utils.sanitizeHTML(task.strike_report)}
                </div>
            ` : ''}
        </div>

        <div class="task-actions">
            <button class="task-action" onclick="openTaskModal('${task.id}')" title="Edit Task">
                <i class="fas fa-edit"></i>
            </button>
            <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                <i class="fas fa-check"></i>
            </button>
            <button class="task-action danger" onclick="deleteTask('${task.id}')" title="Delete Task">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;

    return taskDiv;
}

function sortTasksForDisplay(tasks) {
    // Keep original order for non-struck tasks, move struck ones to the end
    if (!Array.isArray(tasks)) {
        return [];
    }

    return [...tasks].sort((a, b) => {
        const aStruck = a?.struck_today || a?.completed || a?.struck_forever;
        const bStruck = b?.struck_today || b?.completed || b?.struck_forever;

        if (aStruck === bStruck) {
            return 0;
        }
        return aStruck ? 1 : -1;
    });
}

// Task filtering
function filterTasks(tasks, filter) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    switch (filter) {
        case 'active':
            return tasks.filter(task => !task.struck_forever && !task.struck_today);
        case 'completed':
            return tasks.filter(task => task.completed || task.struck_forever);
        case 'today':
            return tasks.filter(task => task.struck_today);
        case 'overdue':
            return tasks.filter(task => {
                if (task.due_date) {
                    const dueDate = new Date(task.due_date);
                    return dueDate < today && !task.struck_forever;
                }
                return false;
            });
        case 'all':
        default:
            return tasks;
    }
}

function setActiveFilter(filter) {
    AppState.set('currentFilter', filter);

    // Update UI
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    const activeTab = document.querySelector(`[data-filter="${filter}"]`);
    if (activeTab) {
        activeTab.classList.add('active');
    }

    // Re-render tasks with the new status filter and current project filter
    renderTasks();
}

function setProjectFilter(filterValue) {
    const value = filterValue || 'all';
    AppState.set('projectFilter', value);

    const select = document.getElementById('project-filter');
    if (select && select.value !== value) {
        select.value = value;
    }

    // Pass project filter directly into global renderTasks so it cannot be lost
    if (typeof renderTasks === 'function') {
        renderTasks(undefined, value);
    } else if (window.Tasks && typeof window.Tasks.renderTasks === 'function') {
        window.Tasks.renderTasks();
    }
}

function updateProjectFilterOptions() {
    const select = document.getElementById('project-filter');
    if (!select || !AppState || !AppState.getTasks) return;

    const tasks = AppState.getTasks() || [];
    const seen = new Set();
    const projects = [];
    let hasNoProject = false;

    tasks.forEach(task => {
        const raw = task.project || '';
        const name = raw.trim();
        if (name) {
            if (!seen.has(name)) {
                seen.add(name);
                projects.push(name);
            }
        } else {
            hasNoProject = true;
        }
    });

    const previous = (typeof AppState !== 'undefined' && AppState.get)
        ? AppState.get('projectFilter') || 'all'
        : (select.value || 'all');

    // Rebuild options
    select.innerHTML = '';

    const optAll = document.createElement('option');
    optAll.value = 'all';
    optAll.textContent = 'All Projects';
    select.appendChild(optAll);

    if (hasNoProject) {
        const optNone = document.createElement('option');
        optNone.value = '__none__';
        optNone.textContent = 'No Project';
        select.appendChild(optNone);
    }

    projects.sort((a, b) => a.localeCompare(b));
    projects.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        select.appendChild(opt);
    });

    // Restore previous selection if still valid; otherwise default to 'all'
    const validValues = new Set(Array.from(select.options).map(o => o.value));
    const target = validValues.has(previous) ? previous : 'all';
    select.value = target;
    AppState.set('projectFilter', target);
}

// Wire up project filter change handler once DOM is ready
if (typeof document !== 'undefined') {
    document.addEventListener('DOMContentLoaded', () => {
        const select = document.getElementById('project-filter');
        if (select) {
            select.addEventListener('change', (e) => {
                setProjectFilter(e.target.value);
            });

            // Initialize from AppState if a project filter is already set
            try {
                const existing = (typeof AppState !== 'undefined' && AppState.get)
                    ? AppState.get('projectFilter') || 'all'
                    : 'all';
                select.value = existing;
            } catch (e) { /* no-op */ }
        }
    });
}

// Drag and drop functionality
function setupDragAndDrop() {
    const tasks = document.querySelectorAll('.task-item');

    tasks.forEach(task => {
        task.addEventListener('dragstart', handleDragStart);
        task.addEventListener('dragend', handleDragEnd);
        task.addEventListener('dragover', handleDragOver);
        task.addEventListener('drop', handleDrop);
    });
}

function handleDragStart(e) {
    e.dataTransfer.setData('text/plain', e.target.id);
    e.target.classList.add('dragging');
}

function handleDragEnd(e) {
    e.target.classList.remove('dragging');
}

function handleDragOver(e) {
    e.preventDefault();
    e.target.classList.add('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.target.classList.remove('drag-over');

    const draggedId = e.dataTransfer.getData('text/plain');
    const draggedElement = document.getElementById(draggedId);

    if (draggedElement && e.target !== draggedElement) {
        // Simple reordering - in a real app, you'd want to persist the order
        const container = e.target.parentNode;
        const tasks = Array.from(container.children);
        const draggedIndex = tasks.indexOf(draggedElement);
        const targetIndex = tasks.indexOf(e.target);

        if (draggedIndex < targetIndex) {
            container.insertBefore(draggedElement, e.target.nextSibling);
        } else {
            container.insertBefore(draggedElement, e.target);
        }
    }
}

// Modal management for tasks
function openStrikeModal(taskId) {
    AppState.set('strikeTaskId', taskId);
    const modal = document.getElementById('strike-modal');
    modal.style.display = 'flex';
}

function closeStrikeModal() {
    const modal = document.getElementById('strike-modal');
    modal.style.display = 'none';
    AppState.set('strikeTaskId', null);
}

function openScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    modal.style.display = 'flex';
}

function closeScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    modal.style.display = 'none';
}

function confirmSchedule() {
    // Schedule task logic would go here
    closeScheduleModal();
    Utils.safeShowNotification('Task scheduled successfully!', 'success');
}

// Task statistics
async function updateTaskStats() {
    const tasks = AppState.getTasks();
    const stats = {
        total: tasks.length,
        active: tasks.filter(t => !t.struck_forever && !t.struck_today).length,
        completed: tasks.filter(t => t.completed || t.struck_forever).length,
        today: tasks.filter(t => t.struck_today).length,
        overdue: tasks.filter(t => {
            if (t.due_date) {
                const dueDate = new Date(t.due_date);
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                return dueDate < today && !t.struck_forever;
            }
            return false;
        }).length
    };

    // Update UI elements if they exist
    const elements = {
        'total-tasks': stats.total,
        'active-tasks': stats.active,
        'completed-tasks': stats.completed,
        'today-tasks': stats.today,
        'overdue-tasks': stats.overdue
    };

    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });

    // Update mini analytics in tasks header from decoupled analytics endpoint (does not reset with daily strike reset)
    const headerStrikedToday = document.getElementById('header-striked-today');
    if (headerStrikedToday) {
        try {
            const resp = await apiCall('/api/analytics');
            const a = await resp.json();
            if (a && a.success) {
                headerStrikedToday.textContent = a.today_strikes ?? 0;
            } else {
                headerStrikedToday.textContent = stats.today; // fallback
            }
        } catch (e) {
            headerStrikedToday.textContent = stats.today; // fallback
        }
    }
    
    // Also check if mini-analytics container exists
    const miniAnalytics = document.querySelector('.mini-analytics');
    if (miniAnalytics) {
        // no-op
    }
}

// Export functions for use in other modules
// Ensure DOM classes match current task flags (used after resets)
function syncStrikeClassesFromState() {
    try {
        const tasks = AppState.getTasks();
        tasks.forEach(t => {
            const el = document.getElementById(`task-${t.id}`);
            if (!el) return;
            // Container classes
            el.classList.remove('struck-today', 'struck-forever');
            if (t.struck_today) el.classList.add('struck-today');
            if (t.completed || t.struck_forever) el.classList.add('struck-forever');
            // Title classes
            const title = el.querySelector('.task-title');
            if (title) {
                title.classList.toggle('struck', Boolean(t.struck_today || t.completed || t.struck_forever));
            }
        });
    } catch (e) { /* no-op */ }
}

window.Tasks = {
    loadTasks,
    saveTask,
    saveQuickTask,
    updateTask,
    deleteTask,
    strikeTaskToday,
    strikeTaskForever,
    getTaskFormData,
    getQuickTaskFormData,
    openTaskModal,
    closeTaskModal,
    openQuickAddModal,
    closeQuickAddModal,
    renderTasks,
    createTaskElement,
    filterTasks,
    setActiveFilter,
    setProjectFilter,
    updateProjectFilterOptions,
    setupDragAndDrop,
    openStrikeModal,
    closeStrikeModal,
    openScheduleModal,
    closeScheduleModal,
    confirmSchedule,
    updateTaskStats,
    sortTasksForDisplay,
    syncStrikeClassesFromState
};
