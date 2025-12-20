// Retry Task functionality - simple date picker to reschedule expired tasks

let currentRetryTaskId = null;

function openRetryModal(taskId) {
    if (!taskId) {
        showNotification('No task selected', 'error');
        return;
    }

    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    
    if (!task) {
        showNotification('Task not found', 'error');
        return;
    }

    currentRetryTaskId = taskId;
    
    // Open the retry modal
    const modal = document.getElementById('retry-modal');
    const titleEl = document.getElementById('retry-task-title');
    const dateInput = document.getElementById('retry-date');
    
    if (modal && titleEl && dateInput) {
        titleEl.textContent = task.title;
        
        // Set min to today, default to tomorrow
        const today = new Date();
        const todayYy = today.getFullYear();
        const todayMm = String(today.getMonth() + 1).padStart(2, '0');
        const todayDd = String(today.getDate()).padStart(2, '0');
        const todayStr = `${todayYy}-${todayMm}-${todayDd}`;
        
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        const yy = tomorrow.getFullYear();
        const mm = String(tomorrow.getMonth() + 1).padStart(2, '0');
        const dd = String(tomorrow.getDate()).padStart(2, '0');
        const tomorrowStr = `${yy}-${mm}-${dd}`;
        
        dateInput.value = tomorrowStr;
        dateInput.min = todayStr; // Allow today and future dates
        
        modal.style.display = 'flex';
        modal.classList.add('active');
        dateInput.focus();
    }
}

function closeRetryModal() {
    const modal = document.getElementById('retry-modal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
    currentRetryTaskId = null;
}

async function confirmRetry() {
    if (!currentRetryTaskId) {
        showNotification('No task selected', 'error');
        return;
    }
    
    const dateInput = document.getElementById('retry-date');
    const newDate = dateInput ? dateInput.value : null;
    
    if (!newDate) {
        showNotification('Please select a date', 'error');
        return;
    }
    
    try {
        // Get the current task to preserve all fields
        const tasks = AppState.getTasks();
        const task = tasks.find(t => t.id === currentRetryTaskId);
        
        if (!task) {
            showNotification('Task not found', 'error');
            return;
        }
        
        // Update the task with new due date, preserving all other fields
        const response = await fetch(`/api/tasks/${currentRetryTaskId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: task.title,
                description: task.description || '',
                priority: task.priority || 'medium',
                project: task.project || '',
                due_date: newDate,
                estimated_duration: task.estimated_duration || task.duration || 60
            })
        });
        
        if (response.ok) {
            // Track retry event (optional, backend endpoint may not exist yet)
            try {
                await fetch(`/api/tasks/${currentRetryTaskId}/retry`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ new_date: newDate })
                });
            } catch (e) {
                // Retry tracking failed, but task update succeeded
                console.warn('Failed to track retry event:', e);
            }
            
            closeRetryModal();
            await loadTasks();
            updateDashboardStats();
            showNotification('Task rescheduled successfully! 🔄', 'success');
        } else {
            const error = await response.json();
            showNotification(error.error || 'Failed to reschedule task', 'error');
        }
    } catch (error) {
        console.error('Error retrying task:', error);
        showNotification('Error rescheduling task', 'error');
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    const closeBtn = document.getElementById('close-retry-modal');
    const cancelBtn = document.getElementById('cancel-retry');
    const confirmBtn = document.getElementById('confirm-retry');
    
    if (closeBtn) closeBtn.addEventListener('click', closeRetryModal);
    if (cancelBtn) cancelBtn.addEventListener('click', closeRetryModal);
    if (confirmBtn) confirmBtn.addEventListener('click', confirmRetry);
    
    // Close on backdrop click
    const modal = document.getElementById('retry-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeRetryModal();
        });
    }
});

// Main retry function called from task cards
async function retryTask(taskId) {
    openRetryModal(taskId);
}

// Make functions globally available
window.retryTask = retryTask;
window.openRetryModal = openRetryModal;
window.closeRetryModal = closeRetryModal;
window.confirmRetry = confirmRetry;
