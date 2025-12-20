// Schedule Modal Functions
let currentScheduleTaskId = null;

function openScheduleModal() {
    // Get available tasks (not scheduled) from AppState
    const allTasks = AppState.get('tasks') || [];
    const availableTasks = allTasks.filter(task => !task.completed);
    
    if (availableTasks.length === 0) {
        showNotification('No available tasks to schedule', 'info');
        return;
    }
    
    // Populate the existing task selector
    const taskSelect = document.getElementById('schedule-task-select');
    if (taskSelect) {
    taskSelect.innerHTML = '<option value="">Select a task</option>' + 
        availableTasks.map(task => `<option value="${task.id}">${task.title}</option>`).join('');
    }
    
    // Show the modal
    const modal = document.getElementById('schedule-modal');
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex';
    }
}

function closeScheduleModal() {
    const modal = document.getElementById('schedule-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    
    // Clear form
    const hourSelect = document.getElementById('schedule-hour');
    const durationSelect = document.getElementById('schedule-duration');
    const taskSelect = document.getElementById('schedule-task-select');
    const taskTitleInput = document.getElementById('schedule-task-title');
    const taskDescriptionInput = document.getElementById('schedule-task-description');
    const taskProjectInput = document.getElementById('schedule-task-project');
    
    if (hourSelect) hourSelect.value = '';
    if (durationSelect) durationSelect.value = '30';
    if (taskSelect) taskSelect.value = '';
    if (taskTitleInput) taskTitleInput.value = '';
    if (taskDescriptionInput) taskDescriptionInput.value = '';
    if (taskProjectInput) taskProjectInput.value = '';
    
    currentScheduleTaskId = null;
}

async function confirmSchedule() {
    console.log('confirmSchedule called');
    
    const taskSelect = document.getElementById('schedule-task-select');
    const hourSelect = document.getElementById('schedule-hour');
    const durationSelect = document.getElementById('schedule-duration');
    const taskTitleInput = document.getElementById('schedule-task-title');
    const taskDescriptionInput = document.getElementById('schedule-task-description');
    const taskProjectInput = document.getElementById('schedule-task-project');
    
    console.log('Elements found:', {
        taskSelect: !!taskSelect,
        hourSelect: !!hourSelect,
        durationSelect: !!durationSelect,
        taskTitleInput: !!taskTitleInput,
        taskDescriptionInput: !!taskDescriptionInput,
        taskProjectInput: !!taskProjectInput
    });
    
    if (!taskSelect || !hourSelect || !durationSelect || !taskTitleInput || !taskDescriptionInput || !taskProjectInput) {
        console.error('Missing schedule modal elements');
        showNotification('Schedule modal elements not found. Please try again.', 'error');
        return;
    }
    
    const selectedTaskId = taskSelect.value;
    const hour = hourSelect.value;
    const duration = durationSelect.value;
    const newTaskTitle = taskTitleInput.value.trim();
    
    console.log('Values:', { selectedTaskId, hour, duration, newTaskTitle });
    
    if (!hour || !duration) {
        showNotification('Please select time and duration', 'error');
        return;
    }
    
    if (!selectedTaskId && !newTaskTitle) {
        showNotification('Please either select an existing task or enter a new task title', 'error');
        return;
    }
    
    try {
        let taskId = selectedTaskId;
        
        // If creating a new task
        if (!selectedTaskId && newTaskTitle) {
            console.log('Creating new task for scheduling');
            const newTaskData = {
                title: newTaskTitle,
                description: taskDescriptionInput.value.trim(),
                project: taskProjectInput.value.trim(),
                estimated_duration: parseInt(duration)
            };
            
            const createResponse = await Utils.makeAuthenticatedRequest('/api/tasks', {
            method: 'POST',
                body: JSON.stringify(newTaskData)
            });
            
            if (!createResponse.ok) {
                throw new Error('Failed to create new task');
            }
            
            const createdTask = await createResponse.json();
            taskId = createdTask.id;
            console.log('New task created:', createdTask);
        }
        
        // Schedule the task
        console.log('Scheduling task:', taskId);
        const response = await Utils.makeAuthenticatedRequest(`/api/tasks/${taskId}/schedule`, {
            method: 'POST',
            body: JSON.stringify({
                hour: hour,
                duration: parseInt(duration),
                date: (() => {
                    const d = new Date();
                    const yy = d.getFullYear();
                    const mm = String(d.getMonth() + 1).padStart(2, '0');
                    const dd = String(d.getDate()).padStart(2, '0');
                    return `${yy}-${mm}-${dd}`;
                })()
            })
        });
        
if (response.ok) {
            closeScheduleModal();
            loadScheduledTasks();
            showNotification('Task scheduled successfully! 📅', 'success');
            addLog('success', `Task ${taskId} scheduled for ${hour} (${duration} min)`);
            // Refresh tasks to show the scheduled task
            Tasks.loadTasks();
            try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
        } else {
            throw new Error('Failed to schedule task');
        }
        
    } catch (error) {
        console.error('Error scheduling task:', error);
        addLog('error', `Failed to schedule task: ${error.message}`);
        showNotification('Error scheduling task', 'error');
    }
}

async function unscheduleTask(taskId) {
    if (!confirm('Are you sure you want to remove this task from the planner?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/unschedule`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            // FIXED: Reload both available and scheduled tasks
            await loadTasks(); // Refresh global tasks array
            if (typeof window.ensurePlannerV2Init === 'function') {
                window.ensurePlannerV2Init();
            } else if (typeof loadPlannerData === 'function') {
                loadPlannerData(); // Legacy fallback
            }
            showNotification('Task removed from planner! ↩️', 'success');
            Utils.Logger.log(`Task ${taskId} unscheduled`);
        } else {
            throw new Error('Failed to unschedule task');
        }
    } catch (error) {
        Utils.Logger.error('Error unscheduling task:', error);
        showNotification('Error removing task from planner', 'error');
    }
}
