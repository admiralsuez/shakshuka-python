/**
 * Tasks Page Module
 * Handles all task-related functionality
 */

// Task management functions
const TaskManager = {
    async loadTasks() {
        try {
            const tasks = await TaskAPI.getAll();
            AppState.setTasks(Array.isArray(tasks) ? tasks : []);
            return tasks;
        } catch (error) {
            Logger.error('Failed to load tasks:', error);
            throw error;
        }
    },

    async createTask(taskData) {
        try {
            const newTask = await TaskAPI.create(taskData);
            AppState.addTask(newTask);
            this.updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                this.renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
                this.renderRecentTasks();
            }
            
            safeShowNotification('Task created successfully!', 'success');
            return newTask;
        } catch (error) {
            Logger.error('Error creating task:', error);
            safeShowNotification(error.message || 'Error creating task', 'error');
            throw error;
        }
    },

    async updateTask(taskId, taskData) {
        try {
            const updatedTask = await TaskAPI.update(taskId, taskData);
            AppState.updateTask(taskId, updatedTask);
            
            this.updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                this.renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
                this.renderRecentTasks();
            }
            
            safeShowNotification('Task updated successfully!', 'success');
            return updatedTask;
        } catch (error) {
            Logger.error('Error updating task:', error);
            safeShowNotification('Error updating task', 'error');
            throw error;
        }
    },

    async deleteTask(taskId) {
        try {
            await TaskAPI.delete(taskId);
            AppState.removeTask(taskId);
            this.updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                this.renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
                this.renderRecentTasks();
            }
            
            safeShowNotification('Task deleted successfully!', 'success');
        } catch (error) {
            Logger.error('Error deleting task:', error);
            safeShowNotification('Error deleting task', 'error');
            throw error;
        }
    },

    async completeTask(taskId) {
        try {
            const completedTask = await TaskAPI.complete(taskId);
            AppState.updateTask(taskId, completedTask);
            
            this.updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                this.renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
                this.renderRecentTasks();
            }
            
            safeShowNotification('Task completed! 🎉', 'success');
        } catch (error) {
            Logger.error('Error completing task:', error);
            safeShowNotification('Error completing task', 'error');
            throw error;
        }
    },

    renderTasks(filter = 'active') {
        const tasksList = document.getElementById('tasks-list');
        if (!tasksList) return;

        const tasks = AppState.getTasks();
        const sortedTasks = this.getSortedTasks(tasks, filter);

        if (sortedTasks.length === 0) {
            tasksList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-tasks" style="font-size: 3rem; color: #FFB6C1; margin-bottom: 1rem;"></i>
                    <h3>No tasks found</h3>
                    <p>Create your first task to get started!</p>
                </div>
            `;
            return;
        }

        if (AppState.get('currentLayout') === 'grid') {
            tasksList.innerHTML = this.renderGridLayout(sortedTasks);
        } else {
            tasksList.innerHTML = this.renderListLayout(sortedTasks);
        }
    },

    getSortedTasks(tasks, filter) {
        let filteredTasks = tasks;

        // Apply filter
        switch (filter) {
            case 'active':
                filteredTasks = tasks.filter(task => !task.completed);
                break;
            case 'completed':
                filteredTasks = tasks.filter(task => task.completed);
                break;
            case 'expired':
                const today = new Date().toISOString().split('T')[0];
                filteredTasks = tasks.filter(task => 
                    !task.completed && task.due_date && task.due_date < today
                );
                break;
        }

        // Sort tasks
        return filteredTasks.sort((a, b) => {
            // Prioritize struck tasks
            const aStruck = a.struck_today || false;
            const bStruck = b.struck_today || false;
            
            if (aStruck && !bStruck) return 1;
            if (!aStruck && bStruck) return -1;
            
            // If both are struck or neither are struck, maintain original order
            return 0;
        });
    },

    renderGridLayout(tasks) {
        return `
            <div class="tasks-grid">
                ${tasks.map(task => this.renderTaskCard(task)).join('')}
            </div>
        `;
    },

    renderListLayout(tasks) {
        return `
            <div class="tasks-list">
                ${tasks.map(task => this.renderTaskItem(task)).join('')}
            </div>
        `;
    },

    renderTaskCard(task) {
        const maxStrikes = 8;
        const currentStrikes = task.strike_count || 0;
        const progressPercentage = task.completed ? 100 : Math.min((currentStrikes / maxStrikes) * 100, 100);
        
        return `
            <div class="task-card" data-task-id="${task.id}">
                <div class="task-header">
                    <h3>${escapeHtml(task.title)}</h3>
                    <div class="task-actions">
                        <button class="btn-icon" onclick="TaskManager.editTask('${task.id}')" title="Edit">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn-icon" onclick="TaskManager.deleteTask('${task.id}')" title="Delete">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="task-content">
                    <p>${escapeHtml(task.description || '')}</p>
                    <div class="task-progress">
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${progressPercentage}%"></div>
                        </div>
                        <span class="progress-text">${currentStrikes}/${maxStrikes}</span>
                    </div>
                </div>
            </div>
        `;
    },

    renderTaskItem(task) {
        return `
            <div class="task-item" data-task-id="${task.id}">
                <div class="task-content">
                    <h3>${escapeHtml(task.title)}</h3>
                    <p>${escapeHtml(task.description || '')}</p>
                </div>
                <div class="task-actions">
                    <button class="btn-icon" onclick="TaskManager.editTask('${task.id}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-icon" onclick="TaskManager.deleteTask('${task.id}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `;
    },

    updateDashboardStats() {
        const tasks = AppState.getTasks();
        const today = new Date().toISOString().split('T')[0];
        
        const completedToday = tasks.filter(task => 
            task.completed && task.completed_at && 
            task.completed_at.startsWith(today)
        ).length;
        
        const expiredTasks = tasks.filter(task => 
            !task.completed && task.due_date && task.due_date < today
        ).length;
        
        // Update stats display
        const completedElement = document.getElementById('completed-today');
        const expiredElement = document.getElementById('expired-tasks');
        
        if (completedElement) completedElement.textContent = completedToday;
        if (expiredElement) expiredElement.textContent = expiredTasks;
    },

    renderRecentTasks() {
        const tasks = AppState.getTasks();
        const recentTasks = tasks
            .filter(task => !task.completed)
            .slice(0, 5);
        
        const container = document.getElementById('recent-tasks-list');
        if (!container) return;
        
        if (recentTasks.length === 0) {
            container.innerHTML = '<p>No recent tasks</p>';
            return;
        }
        
        container.innerHTML = recentTasks.map(task => `
            <div class="recent-task-item">
                <h4>${escapeHtml(task.title)}</h4>
                <p>${escapeHtml(task.description || '')}</p>
            </div>
        `).join('');
    }
};

// Export for use in other modules
export { TaskManager };
