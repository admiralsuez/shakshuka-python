// Loading screen management
const MIN_LOADING_DURATION_MS = 3000;
let loadingScreenShownAt = null;
let loadingTasksTimerId = null;

function hideLoadingScreen() {
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');

    if (!loadingScreen || !appContainer) return;

    const startedAt = loadingScreenShownAt || Date.now();
    const elapsed = Date.now() - startedAt;
    const delay = Math.max(0, MIN_LOADING_DURATION_MS - elapsed);

    const finalizeHide = () => {
        // Stop any loader task animation timers
        if (loadingTasksTimerId) {
            clearTimeout(loadingTasksTimerId);
            loadingTasksTimerId = null;
        }

        // Add fade-out class
        loadingScreen.classList.add('fade-out');

        // Show app container
        appContainer.style.display = 'block';

        // Remove loading screen after fade animation
        setTimeout(() => {
            loadingScreen.style.display = 'none';
        }, 500);
    };

    if (delay > 0) {
        setTimeout(finalizeHide, delay);
    } else {
        finalizeHide();
    }
}

// Show loading screen initially
function showLoadingScreen() {
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');

    if (loadingScreen && appContainer) {
        loadingScreen.style.display = 'flex';
        appContainer.style.display = 'none';
        loadingScreenShownAt = Date.now();
        try { startLoadingTasksAnimation(); } catch (e) { /* no-op */ }
    }
}

async function startLoadingTasksAnimation() {
    const listEl = document.getElementById('loading-active-tasks');
    if (!listEl) return;

    listEl.innerHTML = '';

    // Default placeholder messages if we can't fetch tasks
    let lines = [
        'Collecting today\'s tasks...',
        'Brewing your schedule...',
        'Almost ready...'
    ];

    try {
        const resp = await fetch('/api/tasks');
        if (resp.ok) {
            const data = await resp.json();
            if (Array.isArray(data)) {
                const activeTasks = data.filter(t => !t.completed && !t.struck_forever && !t.struck_today);
                if (activeTasks.length) {
                    lines = activeTasks
                        .map(t => (t.title || '').trim())
                        .filter(Boolean)
                        .slice(0, 7);
                }
            }
        }
    } catch (e) {
        // keep placeholder lines on failure
    }

    let index = 0;
    const intervalMs = 400;

    const step = () => {
        if (!listEl || index >= lines.length) {
            loadingTasksTimerId = null;
            return;
        }
        const li = document.createElement('li');
        li.className = 'loading-folder__task';
        li.textContent = lines[index++];
        listEl.appendChild(li);
        loadingTasksTimerId = setTimeout(step, intervalMs);
    };

    step();
}

// Add Task Options Modal
function showAddTaskOptions() {
    // Create or show a modal with options for different ways to add tasks
    const existingModal = document.getElementById('add-task-options-modal');
    if (existingModal) {
        existingModal.classList.add('active');
        return;
    }

    const modal = document.createElement('div');
    modal.id = 'add-task-options-modal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h2>How would you like to add a task?</h2>
                <span class="close" onclick="closeAddTaskOptions()">&times;</span>
            </div>
            <div class="add-task-options">
                <button class="add-task-option" onclick="Tasks.openQuickAddModal(); closeAddTaskOptions();">
                    <i class="fas fa-bolt"></i>
                    <div>
                        <h3>Quick Add</h3>
                        <p>Add a simple task with just a title</p>
                    </div>
                </button>
                <button class="add-task-option" onclick="Tasks.openTaskModal(); closeAddTaskOptions();">
                    <i class="fas fa-edit"></i>
                    <div>
                        <h3>Full Form</h3>
                        <p>Add a detailed task with description, priority, and project</p>
                    </div>
                </button>
                <button class="add-task-option" onclick="Tasks.openScheduleModal(); closeAddTaskOptions();">
                    <i class="fas fa-calendar-plus"></i>
                    <div>
                        <h3>Schedule Task</h3>
                        <p>Add a task directly to your daily planner</p>
                    </div>
                </button>
                <button class="add-task-option" onclick="openImportModal(); closeAddTaskOptions();">
                    <i class="fas fa-file-import"></i>
                    <div>
                        <h3>Import Tasks</h3>
                        <p>Import multiple tasks from CSV or TXT</p>
                    </div>
                </button>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    modal.classList.add('active');
}

function closeAddTaskOptions() {
    const modal = document.getElementById('add-task-options-modal');
    if (modal) {
        modal.classList.remove('active');
    }
}
