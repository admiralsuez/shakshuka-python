// Daily Planner Version 2 Module
// Enhanced daily planner with multi-day scheduling and improved UX

class DailyPlannerV2 {
    constructor() {
        this.currentDate = new Date();
        this.selectedDate = new Date();
        this.scheduledTasks = new Map(); // Map of date -> hour -> tasks
        this.availableTasks = [];
        this.isInitialized = false;
        this.isModalOpen = false; // Flag to prevent multiple modals
        // Throttle/merge network fetches to cut redundant GETs
        this._loadScheduledPromise = null;
        this._lastScheduleFetch = 0;
        this._historyHandlersAttached = false;
        
        Utils.debugLog('DailyPlannerV2 constructor - selectedDate:', this.selectedDate.toDateString());
        Utils.debugLog('DailyPlannerV2 constructor - getDateKey result:', this.getDateKey(this.selectedDate));
        
        this.init();
    }

    init() {
        if (this.isInitialized) return;
        
        this.setupEventListeners();
        this.generateHoursGrid();
        this.loadAvailableTasks();
        this.requestLoadScheduledTasks(); // Load from backend on init (throttled)
        this.updateDateDisplay();
        this.autoScrollToCurrentHour();
        this.cleanupOverdueIfNeeded();
        
        this.isInitialized = true;
        Utils.debugLog('Daily Planner v2 initialized');
    }

    setupEventListeners() {
        // Date navigation
        document.getElementById('prev-day')?.addEventListener('click', () => {
            this.selectedDate.setDate(this.selectedDate.getDate() - 1);
            this.updateDateDisplay();
            this.updateHourStates();
            this.requestLoadScheduledTasks(); // Fetch from backend for new date (throttled)
            console.log('Navigated to previous day:', this.getDateKey(this.selectedDate));
            // Scroll to top when changing days
            const hoursGrid = document.getElementById('hours-grid');
            if (hoursGrid) {
                hoursGrid.scrollTop = 0;
            }
        });

        this.attachPlannerHistoryHandlers();

        document.getElementById('next-day')?.addEventListener('click', () => {
            this.selectedDate.setDate(this.selectedDate.getDate() + 1);
            this.updateDateDisplay();
            this.updateHourStates();
            this.requestLoadScheduledTasks(); // Fetch from backend for new date (throttled)
            console.log('Navigated to next day:', this.getDateKey(this.selectedDate));
            // Scroll to top when changing days
            const hoursGrid = document.getElementById('hours-grid');
            if (hoursGrid) {
                hoursGrid.scrollTop = 0;
            }
        });

        // Add task button => Quick Add
        document.getElementById('add-task-to-planner')?.addEventListener('click', () => {
            try {
                if (window.Tasks && typeof window.Tasks.openQuickAddModal === 'function') {
                    window.Tasks.openQuickAddModal();
                } else if (typeof openQuickAddModal === 'function') {
                    openQuickAddModal();
                } else {
                    console.warn('Quick Add modal not available; falling back to task modal');
                    this.showAddTaskModal();
                }
            } catch (e) {
                console.warn('Quick Add failed, falling back to task modal', e);
                this.showAddTaskModal();
            }
        });

        // Drag and drop setup is handled in generateHoursGrid and renderAvailableTasks
    }

    attachPlannerHistoryHandlers() {
        if (this._historyHandlersAttached) return;

        const openBtn = document.getElementById('planner-history-btn');
        const closeBtn = document.getElementById('close-planner-history-modal');
        const modal = document.getElementById('planner-history-modal');

        if (openBtn) {
            openBtn.addEventListener('click', () => this.openPlannerHistoryModal());
        }
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closePlannerHistoryModal());
        }
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.closePlannerHistoryModal();
                }
            });
        }

        this._historyHandlersAttached = true;
    }

    closePlannerHistoryModal() {
        const modal = document.getElementById('planner-history-modal');
        if (!modal) return;
        modal.classList.remove('active');
        modal.style.display = 'none';
    }

    async openPlannerHistoryModal() {
        const modal = document.getElementById('planner-history-modal');
        const select = document.getElementById('planner-history-date');
        const content = document.getElementById('planner-history-content');

        if (!modal || !select || !content) return;

        modal.classList.add('active');
        modal.style.display = 'flex';

        content.innerHTML = `
            <div class="loading-changelog">
                <div class="loading-spinner"></div>
                <p>Loading history...</p>
            </div>
        `;

        try {
            const resp = await apiCall('/api/planner-v2/history?limit=7');
            const data = await resp.json();
            if (!data || !data.success) {
                throw new Error((data && data.error) || 'Failed to load history');
            }

            const days = Array.isArray(data.days) ? data.days : [];
            select.innerHTML = '';

            if (!days.length) {
                // Fallback: show the last 7 calendar days even if there are no stored snapshots yet.
                // This keeps the dropdown usable and the content panel can display an empty message per day.
                const fallbackDays = [];
                const base = new Date();
                base.setHours(0, 0, 0, 0);
                for (let i = 0; i < 7; i++) {
                    const d = new Date(base);
                    d.setDate(base.getDate() - i);
                    fallbackDays.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`);
                }

                fallbackDays.forEach(day => {
                    const opt = document.createElement('option');
                    opt.value = day;
                    opt.textContent = day;
                    select.appendChild(opt);
                });

                const loadSelected = async () => {
                    const day = select.value;
                    await this.loadPlannerHistoryForDay(day);
                };

                select.onchange = () => {
                    loadSelected();
                };

                await loadSelected();
                return;
            }

            days.forEach(day => {
                const opt = document.createElement('option');
                opt.value = day;
                opt.textContent = day;
                select.appendChild(opt);
            });

            const loadSelected = async () => {
                const day = select.value;
                await this.loadPlannerHistoryForDay(day);
            };

            select.onchange = () => {
                loadSelected();
            };

            await loadSelected();
        } catch (e) {
            console.error('Failed to load planner history:', e);
            content.innerHTML = '<p style="color: var(--text-secondary);">Unable to load history.</p>';
        }
    }

    formatHistoryTime(hour, minute) {
        if (hour === null || hour === undefined) return 'Unscheduled';
        const h = parseInt(hour, 10);
        const m = parseInt(minute || 0, 10);
        if (Number.isNaN(h) || Number.isNaN(m)) return 'Unscheduled';
        const ampm = h < 12 ? 'AM' : 'PM';
        const displayHour = h === 0 ? 12 : (h > 12 ? h - 12 : h);
        const mm = String(m).padStart(2, '0');
        return `${displayHour}:${mm} ${ampm}`;
    }

    escapeHtml(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    async loadPlannerHistoryForDay(day) {
        const content = document.getElementById('planner-history-content');
        if (!content) return;

        content.innerHTML = `
            <div class="loading-changelog">
                <div class="loading-spinner"></div>
                <p>Loading ${day}...</p>
            </div>
        `;

        try {
            const resp = await apiCall(`/api/planner-v2/history/${encodeURIComponent(day)}`);
            const data = await resp.json();
            if (!data || !data.success) {
                throw new Error((data && data.error) || 'Failed to load day');
            }

            const entries = Array.isArray(data.entries) ? data.entries : [];
            if (!entries.length) {
                content.innerHTML = '<p style="color: var(--text-secondary);">No tasks logged for this day.</p>';
                return;
            }

            const rowsHtml = entries.map(item => {
                const strikes = parseInt(item.strikes_for_day || 0, 10) || 0;
                let status = 'Not struck';
                if (item.strike_mode === 'forever' || item.completed) {
                    status = 'Forever';
                } else if (strikes >= 2) {
                    status = 'Struck twice';
                } else if (strikes === 1 || item.strike_mode === 'today') {
                    status = 'Struck once';
                }
                const timeLabel = this.formatHistoryTime(item.scheduled_hour, item.scheduled_minute);
                const duration = item.scheduled_duration ? `${item.scheduled_duration}m` : '';
                return `
                    <div class="planner-history-row">
                        <div class="planner-history-time">${this.escapeHtml(timeLabel)}</div>
                        <div class="planner-history-title">${this.escapeHtml(item.title || '')}</div>
                        <div class="planner-history-duration">${this.escapeHtml(duration)}</div>
                        <div class="planner-history-status">${this.escapeHtml(status)}</div>
                    </div>
                `;
            }).join('');

            content.innerHTML = `
                <div class="planner-history-list">
                    <div class="planner-history-row planner-history-row--header">
                        <div class="planner-history-time">Time</div>
                        <div class="planner-history-title">Task</div>
                        <div class="planner-history-duration">Dur.</div>
                        <div class="planner-history-status">Strike</div>
                    </div>
                    ${rowsHtml}
                </div>
            `;
        } catch (e) {
            console.error('Failed to load planner history day:', e);
            content.innerHTML = '<p style="color: var(--text-secondary);">Unable to load this day.</p>';
        }
    }

    generateHoursGrid() {
        const hoursGrid = document.getElementById('hours-grid');
        if (!hoursGrid) return;

        // Ensure inline day navigation exists (fallback if header buttons are hidden)
        this.ensureInlineDayNav();

        hoursGrid.innerHTML = '';

        // Generate 30-minute slots from 12 AM to 11:30 PM
        for (let hour = 0; hour <= 23; hour++) {
            for (let minute = 0; minute < 60; minute += 30) {
                const hourSlot = document.createElement('div');
                hourSlot.className = 'hour-slot';
                hourSlot.dataset.hour = hour;
                hourSlot.dataset.minute = minute;

                const hourTime = document.createElement('div');
                hourTime.className = 'hour-time';
                hourTime.textContent = this.formatTime(hour, minute);

                const hourContent = document.createElement('div');
                hourContent.className = 'hour-content';
                hourContent.dataset.hour = hour;
                hourContent.dataset.minute = minute;

                hourSlot.appendChild(hourTime);
                hourSlot.appendChild(hourContent);

                hoursGrid.appendChild(hourSlot);
            }
        }

        this.updateHourStates();
        
        // Setup drag and drop after generating the grid
        this.setupDragAndDrop();
    }

    formatTime(hour, minute) {
        const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
        const ampm = hour < 12 ? 'AM' : 'PM';
        const displayMinute = minute === 0 ? '00' : minute.toString();
        return `${displayHour}:${displayMinute} ${ampm}`;
    }

    formatHour(hour) {
        if (hour === 0) return '12 AM';
        if (hour < 12) return `${hour} AM`;
        if (hour === 12) return '12 PM';
        return `${hour - 12} PM`;
    }

    updateHourStates() {
        const now = new Date();
        const currentHour = now.getHours();
        const currentMinute = now.getMinutes();
        const isToday = this.isSameDay(this.selectedDate, now);

        document.querySelectorAll('.hour-slot').forEach(slot => {
            const hour = parseInt(slot.dataset.hour);
            const minute = parseInt(slot.dataset.minute);
            
            slot.classList.remove('current-hour', 'past-hour');
            
            if (isToday) {
                // Calculate total minutes for comparison
                const slotMinutes = hour * 60 + minute;
                const currentMinutes = currentHour * 60 + currentMinute;
                
                if (slotMinutes === currentMinutes) {
                    slot.classList.add('current-hour');
                } else if (slotMinutes < currentMinutes) {
                    slot.classList.add('past-hour');
                }
            }
        });
    }

    loadAvailableTasks() {
        const availableTasksContainer = document.getElementById('available-tasks');
        if (!availableTasksContainer) {
            console.warn('Available tasks container not found');
            return;
        }

        Utils.debugLog('Loading available tasks for planner v2...');
        
        // Always try to load from API first to ensure we have the latest data
        Utils.debugLog('Loading tasks from API...');
        this.loadAvailableTasksFromAPI();
    }

    async loadAvailableTasksFromAPI() {
        try {
            const response = await apiCall('/api/planner-v2/tasks');
            const data = await response.json();
            
            if (data.success && data.available_tasks) {
                this.availableTasks = data.available_tasks;
                console.log('Loaded available tasks from API:', this.availableTasks.length);
                console.log('Available tasks:', this.availableTasks);
                this.renderAvailableTasks();
            } else {
                console.error('Failed to load available tasks from API:', data.error);
                this.renderAvailableTasks(); // Render empty state
            }
        } catch (error) {
            console.error('Error loading available tasks from API:', error);
            this.renderAvailableTasks(); // Render empty state
        }
    }

    getScheduledTaskIds() {
        const scheduledIds = new Set();
        this.scheduledTasks.forEach((dayTasks) => {
            dayTasks.forEach((hourTasks) => {
                hourTasks.forEach(task => scheduledIds.add(task.id));
            });
        });
        return scheduledIds;
    }

    renderAvailableTasks() {
        const container = document.getElementById('available-tasks');
        if (!container) return;

        container.innerHTML = '';

        if (this.availableTasks.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: var(--text-secondary); padding: 2rem;">No available tasks to schedule</p>';
            return;
        }

        // Use the same HTML structure as the original planner
        container.innerHTML = this.availableTasks.map(task => `
            <div class="draggable-task" data-task-id="${task.id}" draggable="true">
                <h4>${task.title}</h4>
                <p>${task.description || 'No Description'}</p>
            </div>
        `).join('');
        
        // Setup drag and drop for the newly rendered tasks
        this.setupDragAndDrop();
    }

    setupDragAndDrop() {
        Utils.debugLog('Setting up drag and drop for planner v2...');
        
        // Make tasks draggable
        const draggableTasks = document.querySelectorAll('#available-tasks .draggable-task');
        Utils.debugLog('Found draggable tasks:', draggableTasks.length);
        
        draggableTasks.forEach((task, index) => {
            // Skip if already set up
            if (task.dataset.dragSetup === 'true') return;
            
            Utils.debugLog(`Setting up task ${index}:`, task.dataset.taskId, 'draggable:', task.draggable);
            task.draggable = true;
            task.dataset.dragSetup = 'true';
            
            // Use single bound handler to prevent duplicates
            task.addEventListener('dragstart', this.handleDragStart.bind(this));
            task.addEventListener('dragend', this.handleDragEnd.bind(this));
        });

        // Make time slots droppable
        const timeContents = document.querySelectorAll('#hours-grid .hour-content');
        Utils.debugLog('Found time slots:', timeContents.length);
        
        timeContents.forEach(slot => {
            // Skip if already set up
            if (slot.dataset.dropSetup === 'true') return;
            
            slot.dataset.dropSetup = 'true';
            slot.addEventListener('dragover', this.handleDragOver.bind(this));
            slot.addEventListener('drop', this.handleDrop.bind(this));
            slot.addEventListener('dragenter', this.handleDragEnter.bind(this));
            slot.addEventListener('dragleave', this.handleDragLeave.bind(this));
        });
    }

    handleDragStart(e) {
        // Find the task element (in case drag started on child element)
        let taskElement = e.target;
        while (taskElement && !taskElement.dataset.taskId) {
            taskElement = taskElement.parentElement;
        }
        
        if (!taskElement || !taskElement.dataset.taskId) {
            console.error('No task element found for drag start');
            console.log('Original target:', e.target);
            console.log('Task element:', taskElement);
            return;
        }
        
        Utils.debugLog('Drag started for task:', taskElement.dataset.taskId);
        Utils.debugLog('Drag target element:', taskElement);
        Utils.debugLog('Drag target classes:', taskElement.className);
        Utils.debugLog('Dataset:', taskElement.dataset);
        
        e.dataTransfer.setData('text/plain', taskElement.dataset.taskId);
        console.log('Data transfer set to:', taskElement.dataset.taskId);
        taskElement.style.opacity = '0.5';
        taskElement.classList.add('dragging');
    }

    handleDragEnd(e) {
        Utils.debugLog('Drag ended');
        e.target.style.opacity = '1';
        e.target.classList.remove('dragging');
    }

    handleDragOver(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
    }

    handleDragEnter(e) {
        Utils.debugLog('Drag enter on hour:', e.target.dataset.hour, e.target.dataset.minute);
        e.preventDefault();
        e.target.classList.add('drag-over');
    }

    handleDragLeave(e) {
        Utils.debugLog('Drag leave from hour:', e.target.dataset.hour, e.target.dataset.minute);
        e.target.classList.remove('drag-over');
    }

    async handleDrop(e) {
        Utils.debugLog('Drop event triggered');
        e.preventDefault();
        e.target.classList.remove('drag-over');
        
        const taskId = e.dataTransfer.getData('text/plain');
        const hour = e.target.dataset.hour;
        const minute = e.target.dataset.minute;
        
        Utils.debugLog('Drop target element:', e.target);
        Utils.debugLog('Drop target dataset:', e.target.dataset);
        Utils.debugLog('Dropping task:', taskId, 'at time:', `${hour}:${minute}`);
        
        if (!taskId) {
            console.error('No task ID found in drop data');
            return;
        }
        
        if (hour === undefined || minute === undefined) {
            console.error('No hour/minute found in drop target:', e.target);
            console.error('Hour:', hour, 'Minute:', minute);
            return;
        }
        
        // Validate hour and minute are valid numbers
        const hourNum = parseInt(hour);
        const minuteNum = parseInt(minute);
        
        if (isNaN(hourNum) || isNaN(minuteNum)) {
            console.error('Invalid hour or minute values:', hour, minute);
            return;
        }
        
        // Find the task
        const task = this.availableTasks.find(t => t.id === taskId);
        if (!task) {
            console.error('Task not found:', taskId);
            return;
        }

        // Show duration selector modal
        this.showDurationSelector(task, hourNum, minuteNum);
    }

    // Calculate which time slots a task should occupy based on its duration
    calculateTaskSlots(startHour, startMinute, duration) {
        Utils.debugLog('calculateTaskSlots called with:', { startHour, startMinute, duration });
        const slots = [];
        let currentHour = startHour;
        let currentMinute = startMinute;
        let remainingDuration = duration;

        while (remainingDuration > 0) {
            // Calculate how many minutes are left in the current 30-minute slot
            // Slots are at 0 and 30 minutes
            let minutesInCurrentSlot;
            if (currentMinute === 0) {
                minutesInCurrentSlot = 30;
            } else if (currentMinute === 30) {
                minutesInCurrentSlot = 30;
            } else {
                // Shouldn't happen with our 30-minute slots, but handle it
                minutesInCurrentSlot = 30 - (currentMinute % 30);
            }
            
            const minutesToUse = Math.min(remainingDuration, minutesInCurrentSlot);

            Utils.debugLog('  Slot:', { hour: currentHour, minute: currentMinute, duration: minutesToUse });
            slots.push({
                hour: currentHour,
                minute: currentMinute,
                duration: minutesToUse
            });

            remainingDuration -= minutesToUse;

            // Move to next slot (advance by 30 minutes)
            if (currentMinute === 0) {
                currentMinute = 30;
            } else if (currentMinute === 30) {
                currentHour += 1;
                currentMinute = 0;
            } else {
                // Shouldn't happen, but handle it
                currentMinute = 0;
                currentHour += 1;
            }

            // Prevent infinite loop
            if (currentHour > 23 && currentMinute > 30) break;
        }

        Utils.debugLog('calculateTaskSlots returning:', slots.length, 'slots');
        return slots;
    }

    // Render a task across multiple time slots
    renderTaskInSlots(task, startHour, startMinute, duration) {
        const slots = this.calculateTaskSlots(startHour, startMinute, duration);
        
        slots.forEach((slot, index) => {
            // Select the .hour-content element specifically
            const slotElement = document.querySelector(`.hour-content[data-hour="${slot.hour}"][data-minute="${slot.minute}"]`);
            Utils.debugLog('Looking for slot:', slot.hour, ':', slot.minute, 'Found:', slotElement);
            if (slotElement) {
                const taskElement = this.createScheduledTaskElement(task, slot, index === 0);
                slotElement.appendChild(taskElement);
                Utils.debugLog('Task element appended to slot:', slotElement);
            } else {
                console.warn('Slot element not found for', slot.hour, ':', slot.minute);
            }
        });
    }

    showConflictAlert(message) {
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'conflict-alert-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;

        // Create alert modal
        const modal = document.createElement('div');
        modal.className = 'conflict-alert';
        modal.style.cssText = `
            background: white;
            border-radius: 16px;
            padding: 2rem;
            max-width: 400px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: slideUp 0.3s ease;
        `;

        modal.innerHTML = `
            <div style="text-align: center;">
                <div style="font-size: 3rem; margin-bottom: 1rem;">⚠️</div>
                <h3 style="margin: 0 0 1rem 0; color: #dc2626; font-size: 1.4rem;">Schedule Conflict</h3>
                <p style="margin: 0 0 1.5rem 0; color: #666; font-size: 1rem;">${message}</p>
                <button class="ok-btn" style="
                    padding: 0.75rem 2rem;
                    border: none;
                    border-radius: 8px;
                    background: linear-gradient(135deg, #ff8c42 0%, #ff6b6b 100%);
                    color: white;
                    cursor: pointer;
                    font-size: 1rem;
                    font-weight: 600;
                    transition: all 0.2s;
                    box-shadow: 0 4px 12px rgba(255, 140, 66, 0.3);
                ">OK</button>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Cleanup function
        const closeModal = () => {
            if (document.body.contains(overlay)) {
                document.body.removeChild(overlay);
            }
        };

        // Handle OK button
        modal.querySelector('.ok-btn').addEventListener('click', closeModal);

        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeModal();
            }
        });

        // Close on ESC key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    showDurationSelector(task, hour, minute) {
        // Prevent multiple modals from opening
        if (this.isModalOpen) {
            console.log('Modal already open, ignoring...');
            return;
        }
        
        this.isModalOpen = true;
        
        // Check if modal already exists and remove it
        const existingOverlay = document.querySelector('.duration-modal-overlay');
        if (existingOverlay) {
            console.log('Modal already exists, removing...');
            existingOverlay.remove();
        }
        
        // Create modal overlay
        const overlay = document.createElement('div');
        overlay.className = 'duration-modal-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            backdrop-filter: blur(4px);
        `;

        // Create modal
        const modal = document.createElement('div');
        modal.className = 'duration-modal';
        modal.style.cssText = `
            background: white;
            border-radius: 16px;
            padding: 2rem;
            max-width: 400px;
            width: 90%;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            animation: slideUp 0.3s ease;
        `;

        const timeStr = this.formatTime(hour, minute);
        modal.innerHTML = `
            <h3 style="margin: 0 0 0.5rem 0; color: #333; font-size: 1.4rem;">Schedule Task</h3>
            <p style="margin: 0 0 1.5rem 0; color: #666; font-size: 0.95rem;">
                <strong>${task.title}</strong><br>
                Time: ${timeStr}
            </p>
            <div style="margin-bottom: 1.5rem;">
                <label style="display: block; margin-bottom: 0.75rem; color: #555; font-weight: 600; font-size: 0.9rem;">Duration:</label>
                <div class="duration-options" style="display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem;">
                    <button class="duration-btn" data-duration="30" style="
                        padding: 1rem;
                        border: 2px solid #e5e7eb;
                        border-radius: 10px;
                        background: white;
                        cursor: pointer;
                        font-size: 1rem;
                        font-weight: 600;
                        transition: all 0.2s;
                        color: #374151;
                    ">30 minutes</button>
                    <button class="duration-btn" data-duration="60" style="
                        padding: 1rem;
                        border: 2px solid #e5e7eb;
                        border-radius: 10px;
                        background: white;
                        cursor: pointer;
                        font-size: 1rem;
                        font-weight: 600;
                        transition: all 0.2s;
                        color: #374151;
                    ">1 hour</button>
                    <button class="duration-btn" data-duration="90" style="
                        padding: 1rem;
                        border: 2px solid #e5e7eb;
                        border-radius: 10px;
                        background: white;
                        cursor: pointer;
                        font-size: 1rem;
                        font-weight: 600;
                        transition: all 0.2s;
                        color: #374151;
                    ">1.5 hours</button>
                    <button class="duration-btn" data-duration="120" style="
                        padding: 1rem;
                        border: 2px solid #e5e7eb;
                        border-radius: 10px;
                        background: white;
                        cursor: pointer;
                        font-size: 1rem;
                        font-weight: 600;
                        transition: all 0.2s;
                        color: #374151;
                    ">2 hours</button>
                </div>
                <div style="margin-top: 0.75rem;">
                    <label style="display: block; margin-bottom: 0.5rem; color: #555; font-size: 0.85rem;">Custom (minutes):</label>
                    <input type="number" id="custom-duration" min="5" max="480" step="5" placeholder="Enter minutes" style="
                        width: 100%;
                        padding: 0.75rem;
                        border: 2px solid #e5e7eb;
                        border-radius: 8px;
                        font-size: 1rem;
                        box-sizing: border-box;
                    ">
                </div>
            </div>
            <div style="display: flex; gap: 0.75rem; justify-content: flex-end;">
                <button class="cancel-btn" style="
                    padding: 0.75rem 1.5rem;
                    border: 2px solid #e5e7eb;
                    border-radius: 8px;
                    background: white;
                    cursor: pointer;
                    font-size: 1rem;
                    font-weight: 600;
                    color: #6b7280;
                    transition: all 0.2s;
                ">Cancel</button>
                <button class="confirm-btn" style="
                    padding: 0.75rem 1.5rem;
                    border: none;
                    border-radius: 8px;
                    background: linear-gradient(135deg, #ff8c42 0%, #ff6b6b 100%);
                    color: white;
                    cursor: pointer;
                    font-size: 1rem;
                    font-weight: 600;
                    transition: all 0.2s;
                    box-shadow: 0 4px 12px rgba(255, 140, 66, 0.3);
                ">Schedule</button>
            </div>
        `;

        overlay.appendChild(modal);
        document.body.appendChild(overlay);

        // Add CSS animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideUp {
                from {
                    opacity: 0;
                    transform: translateY(20px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            .duration-btn:hover {
                border-color: #ff8c42 !important;
                background: #fff7ed !important;
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(255, 140, 66, 0.2);
            }
            .duration-btn.selected {
                border-color: #ff8c42 !important;
                background: #ff8c42 !important;
                color: white !important;
            }
            .cancel-btn:hover {
                background: #f3f4f6 !important;
            }
            .confirm-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 6px 16px rgba(255, 140, 66, 0.4);
            }
        `;
        document.head.appendChild(style);

        let selectedDuration = task.estimated_duration || 30;

        // Handle duration button clicks
        modal.querySelectorAll('.duration-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                modal.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
                btn.classList.add('selected');
                selectedDuration = parseInt(btn.dataset.duration);
                modal.querySelector('#custom-duration').value = '';
            });
        });

        // Pre-select default duration
        const defaultBtn = modal.querySelector(`[data-duration="${selectedDuration}"]`);
        if (defaultBtn) defaultBtn.classList.add('selected');

        // Handle custom duration input
        const customInput = modal.querySelector('#custom-duration');
        customInput.addEventListener('input', () => {
            if (customInput.value) {
                modal.querySelectorAll('.duration-btn').forEach(b => b.classList.remove('selected'));
                selectedDuration = parseInt(customInput.value);
            }
        });

        // Cleanup function
        const closeModal = () => {
            if (document.body.contains(overlay)) {
                document.body.removeChild(overlay);
            }
            if (document.head.contains(style)) {
                document.head.removeChild(style);
            }
            this.isModalOpen = false;
            console.log('Modal closed, isModalOpen set to false');
        };

        // Handle cancel
        modal.querySelector('.cancel-btn').addEventListener('click', () => {
            closeModal();
        });

        // Handle confirm
        modal.querySelector('.confirm-btn').addEventListener('click', async () => {
            const customValue = customInput.value;
            if (customValue) {
                selectedDuration = parseInt(customValue);
            }

            if (selectedDuration < 5 || selectedDuration > 480) {
                alert('Duration must be between 5 and 480 minutes');
                return;
            }

            closeModal();

            // Schedule the task
            await this.scheduleTaskViaAPI(task.id, hour, minute, selectedDuration);
        });

        // Close on overlay click
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeModal();
            }
        });
        
        // Close on ESC key
        const handleEscape = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', handleEscape);
            }
        };
        document.addEventListener('keydown', handleEscape);
    }

    async scheduleTaskViaAPI(taskId, hour, minute = 0, duration = 30) {
        try {
            console.log('Scheduling task via API:', { taskId, hour, minute, duration });
            
            // Format hour and minute with leading zeros (HH:MM format)
            const formattedHour = String(hour).padStart(2, '0');
            const formattedMinute = String(minute).padStart(2, '0');
            const scheduledHour = `${formattedHour}:${formattedMinute}`;
            
            const requestBody = {
                hour: scheduledHour,  // API expects "HH:MM" string format
                duration: duration,
                date: this.getDateKey(this.selectedDate)
            };
            
            console.log('Request body:', requestBody);
            console.log('API endpoint:', `/api/tasks/${taskId}/schedule`);
            
            const response = await apiCall(`/api/tasks/${taskId}/schedule`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });

            console.log('Response status:', response.status);
            console.log('Response ok:', response.ok);

if (response.ok) {
                console.log('Task scheduled successfully');
                // Refresh the available tasks
                this.loadAvailableTasks();
                // Refresh scheduled tasks
                this.requestLoadScheduledTasks();
                try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
            } else if (response.status === 409) {
                // Conflict error - show user-friendly message
                const errorData = await response.json();
                console.error('Schedule conflict:', errorData);
                
                // Show styled alert modal
                this.showConflictAlert(errorData.message || 'This time slot conflicts with another task');
            } else {
                const errorText = await response.text();
                console.error('Failed to schedule task:', response.status, errorText);
                alert('Failed to schedule task. Please try again.');
            }
        } catch (error) {
            console.error('Error scheduling task:', error);
            alert('An error occurred while scheduling the task.');
        }
    }

    loadScheduledTasks() {
        const dateKey = this.getDateKey(this.selectedDate);
        console.log('=== loadScheduledTasks START ===');
        console.log('Loading scheduled tasks for date:', dateKey);
        console.log('Current scheduledTasks Map size:', this.scheduledTasks.size);
        console.log('Current scheduledTasks Map keys:', Array.from(this.scheduledTasks.keys()));
        
        // Clear ALL existing scheduled tasks from the display (not just current date)
        const existingTasks = document.querySelectorAll('.scheduled-task-v2');
        console.log('Removing all existing scheduled tasks from display:', existingTasks.length);
        existingTasks.forEach(task => {
            task.remove();
        });

        // Load tasks for this date
        const dayTasks = this.scheduledTasks.get(dateKey) || new Map();
        console.log('Day tasks for', dateKey, ':', dayTasks);
        console.log('Day tasks size:', dayTasks.size);
        console.log('Day tasks keys (hours):', Array.from(dayTasks.keys()));
        
        if (dayTasks.size === 0) {
            console.warn('No scheduled tasks found for date:', dateKey);
        }
        
        dayTasks.forEach((tasks, hour) => {
            console.log('Processing hour', hour, 'with', tasks.length, 'tasks:', tasks);
            tasks.forEach(task => {
                // Get task duration and scheduled time
                const duration = task.scheduled_duration || task.estimated_duration || 30;
                const scheduledHour = task.scheduled_hour || hour;
                const scheduledMinute = task.scheduled_minute || 0;
                
                console.log('Rendering task:', task.title, 'at', scheduledHour, ':', scheduledMinute, 'duration:', duration, 'mins');
                
                // Render task across multiple slots if needed
                this.renderTaskInSlots(task, scheduledHour, scheduledMinute, duration);
            });
        });

        this.updateHourStates();
        console.log('=== loadScheduledTasks END ===');
    }

    createScheduledTaskElement(task, slotInfo, isFirstSlot = true) {
        const taskElement = document.createElement('div');
        taskElement.className = 'scheduled-task-v2';
        taskElement.dataset.taskId = task.id;
        taskElement.dataset.date = this.getDateKey(this.selectedDate);
        taskElement.draggable = true;

        const isStruck = Boolean(task.struck_today || task.struck_forever || task.completed);
        const isForever = Boolean(task.struck_forever || task.completed);
        if (isStruck) {
            taskElement.classList.add('struck');
        }
        if (isForever) {
            taskElement.classList.add('struck-forever');
        }

        // Add overflow styling classes
        if (slotInfo && slotInfo.duration) {
            if (isFirstSlot) {
                taskElement.classList.add('task-start');
            } else {
                taskElement.classList.add('task-continuation');
            }
            
            // Add duration indicator
            taskElement.dataset.duration = slotInfo.duration;
        }

        // Only show full task info in the first slot
        if (isFirstSlot) {
            const duration = task.scheduled_duration || task.estimated_duration || 30;
            const badgeHtml = isForever
                ? '<span class="strike-badge forever" title="Completed"><i class="fas fa-check-circle"></i></span>'
                : (isStruck ? '<span class="strike-badge today" title="Struck today"><i class="fas fa-check"></i></span>' : '');
            taskElement.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.5rem; width: 100%;">
                    <span class="task-title" style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${task.title}</span>
                    <span class="task-duration" style="flex-shrink: 0;">${duration}min</span>
                    ${badgeHtml}
                    <button class="task-action strike-btn planner-strike-task ${isStruck ? 'disabled' : ''}" data-task-id="${task.id}" title="Strike Task" style="flex-shrink: 0;" ${isStruck ? 'disabled' : ''}>
                        <i class="fas fa-check"></i>
                    </button>
                    <button class="task-action remove-scheduled-task" data-task-id="${task.id}" title="Remove from schedule" style="flex-shrink: 0;">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            `;

            // Strike task (opens the same strike flow as Tasks page)
            const strikeButton = taskElement.querySelector('.planner-strike-task');
            if (strikeButton && !isStruck) {
                strikeButton.addEventListener('click', (e) => {
                    e.stopPropagation();
                    try {
                        if (typeof openStrikeModal === 'function') {
                            openStrikeModal(task.id);
                        } else if (window.Tasks && typeof window.Tasks.openStrikeModal === 'function') {
                            window.Tasks.openStrikeModal(task.id);
                        }
                    } catch (err) {
                        console.warn('Failed to open strike modal from planner:', err);
                    }
                });
            }

            // Remove task from schedule
            const removeButton = taskElement.querySelector('.remove-scheduled-task');
            if (removeButton) {
                removeButton.addEventListener('click', (e) => {
                    e.stopPropagation();
                    console.log('Remove button clicked for task:', task.id);
                    this.removeTaskFromSchedule(task.id, this.getDateKey(this.selectedDate));
                });
            }
        } else {
            // For continuation slots, show a visual indicator with continuation arrow
            taskElement.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.3rem; width: 100%; opacity: 0.8;">
                    <i class="fas fa-arrow-down" style="font-size: 0.6rem;"></i>
                    <span class="task-continuation-indicator" style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${task.title} (cont.)</span>
                </div>
            `;
            taskElement.classList.add('task-continuation-only');
        }

        // Drag to reschedule
        taskElement.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', task.id);
            e.dataTransfer.setData('action', 'reschedule');
            taskElement.classList.add('dragging');
        });

        taskElement.addEventListener('dragend', () => {
            taskElement.classList.remove('dragging');
        });

        return taskElement;
    }

    removeTaskFromSchedule(taskId, dateKey) {
        // Use the existing API to unschedule the task
        this.unscheduleTaskViaAPI(taskId);
    }

    async unscheduleTaskViaAPI(taskId) {
        try {
            const response = await apiCall(`/api/tasks/${taskId}/unschedule`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

if (response.ok) {
                console.log('Task unscheduled successfully');
                // Optimistically remove from UI immediately
                this.removeScheduledElementsByTaskId(taskId);
                // Refresh the available tasks
                this.loadAvailableTasks();
                // Refresh scheduled tasks
                this.requestLoadScheduledTasks();
                try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
            } else if (response.status === 404) {
                // Task no longer exists (likely deleted) — remove any remnants from planner UI
                console.warn('Unschedule 404: task not found; removing from planner view');
                this.removeScheduledElementsByTaskId(taskId);
                this.loadAvailableTasks();
                this.loadScheduledTasksFromBackend();
            } else {
                console.error('Failed to unschedule task:', response.statusText);
            }
        } catch (error) {
            console.error('Error unscheduling task:', error);
        }
    }

    removeScheduledElementsByTaskId(taskId) {
        try {
            document.querySelectorAll(`.scheduled-task-v2[data-task-id="${taskId}"]`).forEach(el => el.remove());
        } catch (e) { /* no-op */ }
    }

    updateDateDisplay() {
        const dateDisplay = document.getElementById('current-date');
        const inlineDisplay = document.getElementById('current-date-inline');

        const now = new Date();
        const label = this.isSameDay(this.selectedDate, now)
            ? 'Today'
            : this.isSameDay(this.selectedDate, new Date(now.getTime() + 24 * 60 * 60 * 1000))
                ? 'Tomorrow'
                : this.selectedDate.toLocaleDateString();

        if (dateDisplay) dateDisplay.textContent = label;
        if (inlineDisplay) inlineDisplay.textContent = label;
    }

    autoScrollToCurrentHour() {
        const now = new Date();
        const isToday = this.isSameDay(this.selectedDate, now);
        
        console.log('Auto-scroll called:', {
            isToday,
            currentHour: now.getHours(),
            selectedDate: this.selectedDate.toDateString()
        });
        
        if (isToday) {
            const currentHour = now.getHours();
            const currentMinute = now.getMinutes();
            
            // Scroll to one hour ahead of current time for better context
            let targetHour = currentHour + 1;
            let targetMinute = 0;
            
            // Handle edge case where we're at 11:30 PM or later
            if (targetHour > 23) {
                targetHour = 23;
                targetMinute = 30;
            }
            
            const targetElement = document.querySelector(`.hour-slot[data-hour="${targetHour}"][data-minute="${targetMinute}"]`);
            
            console.log('Auto-scroll target:', {
                currentHour,
                currentMinute,
                targetHour,
                targetMinute,
                element: targetElement
            });
            
            if (targetElement) {
                // Add a longer delay to ensure the grid is fully rendered
                setTimeout(() => {
                    console.log('Scrolling to target hour:', targetHour, ':', targetMinute);
                    targetElement.scrollIntoView({ 
                        behavior: 'smooth', 
                        block: 'start' 
                    });
                }, 500);
            } else {
                console.warn('Target hour element not found for hour:', targetHour, 'minute:', targetMinute);
            }
        }
    }

    // Inline day navigation (fallback if header buttons are missing/hidden)
    ensureInlineDayNav() {
        try {
            const hoursSection = document.querySelector('.hours-section');
            const header = hoursSection?.querySelector('h3');
            if (!hoursSection || !header) return;
            
            if (!hoursSection.querySelector('#planner-inline-nav')) {
                const nav = document.createElement('div');
                nav.id = 'planner-inline-nav';
                nav.style.display = 'flex';
                nav.style.alignItems = 'center';
                nav.style.gap = '0.5rem';
                nav.style.marginLeft = 'auto';
                
                nav.innerHTML = `
                    <button id="prev-day-inline" class="date-btn" title="Previous Day"><i class="fas fa-chevron-left"></i></button>
                    <span id="current-date-inline" style="font-weight:600;">${this.isSameDay(this.selectedDate, new Date()) ? 'Today' : this.selectedDate.toLocaleDateString()}</span>
                    <button id="next-day-inline" class="date-btn" title="Next Day"><i class="fas fa-chevron-right"></i></button>
                `;
                
                // Make header a flex row and append nav
                header.style.display = 'flex';
                header.style.alignItems = 'center';
                header.style.justifyContent = 'space-between';
                header.appendChild(nav);
                
                // Bind events
                const bindNav = () => {
                    document.getElementById('prev-day-inline')?.addEventListener('click', () => {
                        this.selectedDate.setDate(this.selectedDate.getDate() - 1);
                        this.updateDateDisplay();
                        this.updateHourStates();
                        this.requestLoadScheduledTasks();
                        const container = document.getElementById('hours-grid');
                        if (container) container.scrollTop = 0;
                        const cd = document.getElementById('current-date-inline');
                        if (cd) cd.textContent = this.isSameDay(this.selectedDate, new Date()) ? 'Today' : this.selectedDate.toLocaleDateString();
                    });
                    document.getElementById('next-day-inline')?.addEventListener('click', () => {
                        this.selectedDate.setDate(this.selectedDate.getDate() + 1);
                        this.updateDateDisplay();
                        this.updateHourStates();
                        this.loadScheduledTasksFromBackend();
                        const container = document.getElementById('hours-grid');
                        if (container) container.scrollTop = 0;
                        const cd = document.getElementById('current-date-inline');
                        if (cd) cd.textContent = this.isSameDay(this.selectedDate, new Date()) ? 'Today' : this.selectedDate.toLocaleDateString();
                    });
                };
                bindNav();
            }
        } catch (e) {
            console.warn('Failed to inject inline day nav:', e);
        }
    }

    // (Removed) available tasks day nav

    isSameDay(date1, date2) {
        return date1.getFullYear() === date2.getFullYear() &&
               date1.getMonth() === date2.getMonth() &&
               date1.getDate() === date2.getDate();
    }

    getDateKey(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    // Cleanup: after 3AM local time, unschedule previous-day tasks that aren't completed
    async cleanupOverdueIfNeeded() {
        try {
            const now = new Date();
            const todayKey = this.getDateKey(now);
            const lastCleanup = localStorage.getItem('planner_v2_last_cleanup');
            if (lastCleanup === todayKey) return; // Already cleaned today
            const resp = await apiCall('/api/planner-v2/cleanup-overdue', { method: 'POST' });
            if (resp.ok) {
                localStorage.setItem('planner_v2_last_cleanup', todayKey);
                // Reload lists to reflect changes
                this.loadAvailableTasks();
                this.requestLoadScheduledTasks();
            }
        } catch (e) {
            console.warn('Cleanup overdue scheduled tasks failed:', e);
        }
        }
        
    showAddTaskModal() {
        // Reuse existing task modal
        const modal = document.getElementById('task-modal');
        const titleElement = document.getElementById('task-modal-title');
        
        if (modal && titleElement) {
            modal.style.display = 'block';
            titleElement.textContent = 'Add Task to Planner';
        } else {
            console.warn('Task modal elements not found');
            // Fallback: show a simple alert or create a basic modal
            alert('Add Task functionality will be available soon. Please use the main "Add Task" button for now.');
        }
    }


    // Throttled requester that coalesces concurrent calls and enforces a minimal interval
    requestLoadScheduledTasks(minIntervalMs = 1500) {
        const now = Date.now();
        if (this._loadScheduledPromise) {
            return this._loadScheduledPromise; // Reuse in-flight request
        }
        if (now - this._lastScheduleFetch < minIntervalMs) {
            return Promise.resolve(); // Too soon; skip
        }
        this._lastScheduleFetch = now;
        this._loadScheduledPromise = this.loadScheduledTasksFromBackend()
            .catch((e) => { console.warn('Scheduled tasks fetch failed', e); })
            .finally(() => { this._loadScheduledPromise = null; });
        return this._loadScheduledPromise;
    }

    loadScheduledTasksFromBackend() {
        console.log('=== loadScheduledTasksFromBackend START ===');
        console.log('Fetching from: /api/planner-v2/schedule');
        // Return the promise chain so callers can await/catch
        return apiCall('/api/planner-v2/schedule')
        .then(response => {
            console.log('Response status:', response.status, response.statusText);
            return response.json();
        })
        .then(data => {
            console.log('Backend response received:', data);
            console.log('Response success:', data.success);
            console.log('Scheduled tasks in response:', data.scheduled_tasks);
            
            if (data.success && data.scheduled_tasks) {
                console.log('Number of scheduled dates:', Object.keys(data.scheduled_tasks).length);
                console.log('Scheduled dates:', Object.keys(data.scheduled_tasks));
                
                // Convert serializable format back to Map
                this.scheduledTasks.clear();
                Object.entries(data.scheduled_tasks).forEach(([dateKey, dayTasks]) => {
                    console.log('Processing date:', dateKey, 'with hours:', Object.keys(dayTasks));
                    const dayMap = new Map();
                    Object.entries(dayTasks).forEach(([hour, tasks]) => {
                        console.log('  Hour', hour, 'has', tasks.length, 'task(s)');
                        tasks.forEach(task => {
                            console.log('    Task:', task.title, 'scheduled_hour:', task.scheduled_hour, 'scheduled_minute:', task.scheduled_minute);
                        });
                        dayMap.set(parseInt(hour), tasks);
                    });
                    this.scheduledTasks.set(dateKey, dayMap);
                });
                
                console.log('Updated scheduledTasks Map size:', this.scheduledTasks.size);
                console.log('Updated scheduledTasks Map keys:', Array.from(this.scheduledTasks.keys()));
                console.log('About to call loadScheduledTasks()...');
                this.loadScheduledTasks();
            } else {
                console.warn('No scheduled tasks found or API error:', data);
            }
            console.log('=== loadScheduledTasksFromBackend END ===');
        })
        .catch(error => {
            console.error('Error loading scheduled tasks:', error);
            console.error('Error stack:', error.stack);
        });
    }

    refresh() {
        this.loadAvailableTasks();
        this.requestLoadScheduledTasks();
        this.updateHourStates();
        this.autoScrollToCurrentHour();
        this.cleanupOverdueIfNeeded();
    }
}

// Lightweight initializer that can be called on demand
window.ensurePlannerV2Init = function ensurePlannerV2Init() {
    if (!window.DailyPlannerV2) {
        window.DailyPlannerV2 = new DailyPlannerV2();
    } else {
        try {
            window.DailyPlannerV2.refresh();
        } catch (e) {
            console.warn('Planner v2 refresh failed, re-initializing...', e);
            window.DailyPlannerV2 = new DailyPlannerV2();
        }
    }
};

// Export for use in other modules (CommonJS)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = DailyPlannerV2;
}
