// Task operation lock to prevent race conditions
let taskOperationLock = false;
const TASK_OPERATION_TIMEOUT = 10000; // 10 seconds

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

async function createTask(taskData) {
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
        
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(taskData)
        });

        console.log('Response status:', response.status);
        console.log('Response ok:', response.ok);

        if (response.ok) {
            console.log('Response is OK, parsing JSON...');
            const newTask = await response.json();
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
        } else {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `Failed to create task (${response.status})`);
        }
    } catch (error) {
        console.error('Error creating task:', error);
        showNotification(error.message || 'Error creating task', 'error');
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
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            const updatedTask = await response.json();
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
        } else {
            throw new Error('Failed to update task');
        }
    } catch (error) {
        console.error('Error updating task:', error);
        if (error.message && error.message.toLowerCase().includes('login')) {
            showNotification('Please log in to update tasks', 'error');
        } else {
            showNotification('Error updating task', 'error');
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
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
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
            
            showNotification('Task deleted successfully!', 'success');
            return true;
        } else {
            throw new Error('Failed to delete task');
        }
    } catch (error) {
        console.error('Error deleting task:', error);
        if (error.message && error.message.toLowerCase().includes('login')) {
            showNotification('Please log in to delete tasks', 'error');
        } else {
            showNotification('Error deleting task', 'error');
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
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });

        if (response.ok) {
            const completedTask = await response.json();
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
        } else {
            throw new Error('Failed to complete task');
        }
    } catch (error) {
        console.error('Error completing task:', error);
        if (error.message && error.message.toLowerCase().includes('login')) {
            showNotification('Please log in to complete tasks', 'error');
        } else {
            showNotification('Error completing task', 'error');
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
    const taskData = {
        title: document.getElementById('task-title').value,
        description: document.getElementById('task-description').value,
        project: document.getElementById('task-project').value,
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
        } else {
            await createTask(taskData);
        }
        
        closeTaskModal();
    } catch (error) {
        console.error('Error saving task:', error);
    } finally {
        // Always reset the flag, even if an error occurs
        window.taskCreationInProgress = false;
    }
}
