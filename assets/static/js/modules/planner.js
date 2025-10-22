/**
 * Planner Module - Handles daily planner, scheduling, and time management
 */

const Planner = (function() {
    'use strict';
    
    let scheduledTasks = [];
    let currentDate = new Date();
    
    // ==================== Initialization ====================
    
    function initialize() {
        setupDateNavigation();
        loadPlanner();
    }
    
    // ==================== Date Navigation ====================
    
    function setupDateNavigation() {
        const prevBtn = document.getElementById('prev-day-btn');
        const nextBtn = document.getElementById('next-day-btn');
        const todayBtn = document.getElementById('today-btn');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => navigateDate(-1));
        }
        
        if (nextBtn) {
            nextBtn.addEventListener('click', () => navigateDate(1));
        }
        
        if (todayBtn) {
            todayBtn.addEventListener('click', goToToday);
        }
        
        updateDateDisplay();
    }
    
    function navigateDate(days) {
        currentDate.setDate(currentDate.getDate() + days);
        updateDateDisplay();
        loadPlanner();
    }
    
    function goToToday() {
        currentDate = new Date();
        updateDateDisplay();
        loadPlanner();
    }
    
    function updateDateDisplay() {
        const dateDisplay = document.getElementById('planner-date');
        if (dateDisplay) {
            const options = { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' };
            dateDisplay.textContent = currentDate.toLocaleDateString('en-US', options);
        }
    }
    
    // ==================== Planner Management ====================
    
    async function loadPlanner() {
        const dateStr = currentDate.toISOString().split('T')[0];
        
        try {
            const response = await fetch(`/api/planner/${dateStr}`);
            if (response.ok) {
                scheduledTasks = await response.json();
                renderPlanner();
            }
        } catch (error) {
            console.error('Error loading planner:', error);
            UI.showError('Failed to load planner');
        }
    }
    
    async function savePlanner() {
        const dateStr = currentDate.toISOString().split('T')[0];
        
        try {
            const response = await fetch(`/api/planner/${dateStr}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ tasks: scheduledTasks })
            });
            
            if (response.ok) {
                UI.showSuccess('Planner saved');
                return true;
            }
            
            UI.showError('Failed to save planner');
            return false;
        } catch (error) {
            console.error('Error saving planner:', error);
            UI.showError('Error saving planner');
            return false;
        }
    }
    
    // ==================== Rendering ====================
    
    function renderPlanner() {
        const plannerContainer = document.getElementById('planner-grid');
        if (!plannerContainer) return;
        
        plannerContainer.innerHTML = '';
        
        // Generate time slots (24 hours)
        for (let hour = 0; hour < 24; hour++) {
            const timeSlot = createTimeSlot(hour);
            plannerContainer.appendChild(timeSlot);
        }
    }
    
    function createTimeSlot(hour) {
        const slot = document.createElement('div');
        slot.className = 'time-slot';
        slot.dataset.hour = hour;
        
        const timeLabel = document.createElement('div');
        timeLabel.className = 'time-label';
        timeLabel.textContent = formatHour(hour);
        
        const taskArea = document.createElement('div');
        taskArea.className = 'task-area';
        
        // Add tasks for this hour
        const tasksAtHour = scheduledTasks.filter(t => getTaskHour(t) === hour);
        tasksAtHour.forEach(task => {
            const taskElement = createPlannerTaskElement(task);
            taskArea.appendChild(taskElement);
        });
        
        // Make droppable
        taskArea.addEventListener('dragover', handleDragOver);
        taskArea.addEventListener('drop', (e) => handleDrop(e, hour));
        
        slot.appendChild(timeLabel);
        slot.appendChild(taskArea);
        
        return slot;
    }
    
    function createPlannerTaskElement(task) {
        const element = document.createElement('div');
        element.className = `planner-task priority-${task.priority}`;
        element.draggable = true;
        element.dataset.taskId = task.id;
        
        element.innerHTML = `
            <div class="planner-task-title">${escapeHtml(task.title)}</div>
            <div class="planner-task-time">${task.startTime} - ${task.endTime}</div>
            <button class="planner-task-remove" onclick="Planner.removeTaskFromPlanner('${task.id}')">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        element.addEventListener('dragstart', handleDragStart);
        
        return element;
    }
    
    // ==================== Task Scheduling ====================
    
    async function scheduleTask(taskId, hour, duration = 1) {
        const startTime = `${String(hour).padStart(2, '0')}:00`;
        const endHour = hour + duration;
        const endTime = `${String(endHour).padStart(2, '0')}:00`;
        
        // Get task details
        const task = await Tasks.getTaskById(taskId);
        if (!task) return false;
        
        const scheduledTask = {
            id: taskId,
            title: task.title,
            startTime,
            endTime,
            hour,
            priority: task.priority
        };
        
        scheduledTasks.push(scheduledTask);
        await savePlanner();
        renderPlanner();
        
        return true;
    }
    
    function removeTaskFromPlanner(taskId) {
        scheduledTasks = scheduledTasks.filter(t => t.id !== taskId);
        savePlanner();
        renderPlanner();
    }
    
    // ==================== Drag and Drop ====================
    
    let draggedTask = null;
    
    function handleDragStart(e) {
        draggedTask = e.target.dataset.taskId;
        e.dataTransfer.effectAllowed = 'move';
    }
    
    function handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        return false;
    }
    
    function handleDrop(e, hour) {
        e.preventDefault();
        e.stopPropagation();
        
        if (draggedTask) {
            scheduleTask(draggedTask, hour);
            draggedTask = null;
        }
        
        return false;
    }
    
    // ==================== Utilities ====================
    
    function formatHour(hour) {
        const period = hour < 12 ? 'AM' : 'PM';
        const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
        return `${displayHour}:00 ${period}`;
    }
    
    function getTaskHour(task) {
        if (task.hour !== undefined) return task.hour;
        if (task.startTime) {
            const [hour] = task.startTime.split(':');
            return parseInt(hour);
        }
        return 0;
    }
    
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    // ==================== Public API ====================
    
    return {
        initialize,
        loadPlanner,
        savePlanner,
        scheduleTask,
        removeTaskFromPlanner,
        navigateDate,
        goToToday
    };
})();

// Expose to global scope
window.Planner = Planner;

