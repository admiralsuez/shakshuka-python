// Tasks Module

// Task management functions
async function loadTasks() {
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/tasks');
        const tasks = await response.json();

        AppState.setTasks(tasks);
        renderTasks();
        updateTaskStats();
        Logger.info(`Loaded ${tasks.length} tasks`);
    } catch (error) {
        Logger.error('Failed to load tasks:', error);
        Utils.safeShowNotification('Failed to load tasks', 'error');
    }
}

async function saveTask() {
    const taskData = getTaskFormData();
    if (!taskData) return;

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            closeTaskModal();
            loadTasks();
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
        const response = await Utils.makeAuthenticatedRequest('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(quickTaskData)
        });

        if (response.ok) {
            closeQuickAddModal();
            loadTasks();
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
        const response = await Utils.makeAuthenticatedRequest(`/api/tasks/${taskId}`, {
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
        const response = await Utils.makeAuthenticatedRequest(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            loadTasks();
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
        const response = await Utils.makeAuthenticatedRequest(`/api/tasks/${taskId}/strike`, {
            method: 'POST',
            body: JSON.stringify({ type: 'today' })
        });

        if (response.ok) {
            closeStrikeModal();
            loadTasks();
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
        const response = await Utils.makeAuthenticatedRequest(`/api/tasks/${taskId}/strike`, {
            method: 'POST',
            body: JSON.stringify({ type: 'forever' })
        });

        if (response.ok) {
            closeStrikeModal();
            loadTasks();
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
    const filter = AppState.get('currentFilter');
    const filteredTasks = filterTasks(tasks, filter);

    const tasksContainer = document.getElementById('tasks-container');
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

function createTaskElement(task) {
    const taskDiv = document.createElement('div');
    taskDiv.className = `task-item ${task.status || 'pending'}`;
    taskDiv.id = `task-${task.id}`;
    taskDiv.draggable = true;

    if (task.struck_today) taskDiv.classList.add('struck-today');
    if (task.struck_forever) taskDiv.classList.add('struck-forever');

    taskDiv.innerHTML = `
        <div class="task-project-tag">
            <span class="project-tag ${task.project ? '' : 'no-project'}">
                ${task.project || 'No Project'}
            </span>
        </div>

        <div class="task-content">
            <h3 class="task-title ${task.struck_today || task.struck_forever ? 'struck' : ''}">
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
            <button class="task-action" onclick="openStrikeModal('${task.id}')" title="Mark as Complete">
                <i class="fas fa-check"></i>
            </button>
            <button class="task-action danger" onclick="deleteTask('${task.id}')" title="Delete Task">
                <i class="fas fa-trash"></i>
            </button>
        </div>
    `;

    return taskDiv;
}

// Task filtering
function filterTasks(tasks, filter) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    switch (filter) {
        case 'active':
            return tasks.filter(task => !task.struck_forever && !task.struck_today);
        case 'completed':
            return tasks.filter(task => task.struck_forever);
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
    document.querySelector(`[data-filter="${filter}"]`).classList.add('active');
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
function updateTaskStats() {
    const tasks = AppState.getTasks();
    const stats = {
        total: tasks.length,
        active: tasks.filter(t => !t.struck_forever && !t.struck_today).length,
        completed: tasks.filter(t => t.struck_forever).length,
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
}

// Export functions for use in other modules
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
    setupDragAndDrop,
    openStrikeModal,
    closeStrikeModal,
    openScheduleModal,
    closeScheduleModal,
    confirmSchedule,
    updateTaskStats
};
