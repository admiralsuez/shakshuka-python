// Global variables
let currentPage = 'tasks';
let tasks = [];
let currentDate = new Date();
let editingTaskId = null;
let currentSettings = {};
let currentLayout = 'list';
let dailyResetTimer = null;
let developerLogs = [];
let currentFilter = 'active'; // Track current filter
let isAuthenticated = false;
let passwordSet = false;

// Helper function to safely add event listeners
function safeAddEventListener(elementId, event, handler) {
    const element = document.getElementById(elementId);
    if (element) {
        element.addEventListener(event, handler);
    } else {
        console.warn(`Element with ID '${elementId}' not found, skipping event listener`);
    }
}

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    initializeApp();
    setupEventListeners();
    checkAuthStatus();
});

// Developer Logging Functions
function initializeLogging() {
    // Override console methods to capture logs
    const originalConsole = {
        log: console.log,
        error: console.error,
        warn: console.warn,
        info: console.info
    };

    console.log = function(...args) {
        originalConsole.log.apply(console, args);
        addLog('info', args.join(' '));
    };

    console.error = function(...args) {
        originalConsole.error.apply(console, args);
        addLog('error', args.join(' '));
    };

    console.warn = function(...args) {
        originalConsole.warn.apply(console, args);
        addLog('warning', args.join(' '));
    };

    console.info = function(...args) {
        originalConsole.info.apply(console, args);
        addLog('info', args.join(' '));
    };

    // Log application startup
    addLog('success', 'Shakshuka application started');
}

function addLog(level, message) {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = {
        timestamp,
        level,
        message,
        id: Date.now() + Math.random()
    };
    
    developerLogs.push(logEntry);
    
    // Keep only last 100 logs to prevent memory issues
    if (developerLogs.length > 100) {
        developerLogs = developerLogs.slice(-100);
    }
}

function displayLogs() {
    const logsContent = document.getElementById('logs-content');
    if (!logsContent) return;

    if (developerLogs.length === 0) {
        logsContent.textContent = 'No logs available';
        return;
    }

    const logsHtml = developerLogs.map(log => {
        return `<div class="log-entry ${log.level}">
            <div class="log-timestamp">[${log.timestamp}]</div>
            <div class="log-message">${log.message}</div>
        </div>`;
    }).join('');

    logsContent.innerHTML = logsHtml;
}

// Authentication Functions
async function checkAuthStatus() {
    try {
        console.log('Checking authentication status...');
        const response = await fetch('/api/auth/status');
        const data = await response.json();
        
        console.log('Auth status response:', data);
        
        isAuthenticated = data.authenticated;
        passwordSet = data.password_set;
        
        console.log('isAuthenticated:', isAuthenticated, 'passwordSet:', passwordSet);
        
        // Check if encrypted files exist by trying to access tasks
        const tasksResponse = await fetch('/api/tasks');
        console.log('Tasks response status:', tasksResponse.status);
        
        if (!passwordSet && tasksResponse.status === 401) {
            // No password set but tasks endpoint requires auth - show setup
            console.log('No password set, showing setup modal');
            showAuthModal('setup');
        } else if (!isAuthenticated) {
            // Password set but not logged in - show login form
            console.log('Not authenticated, showing login modal');
            showAuthModal('login');
        } else {
            // Authenticated - load the app
            console.log('Authenticated, loading app data');
            loadAppData();
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
        // If we can't check status, assume first run
        console.log('Error checking auth, showing setup modal');
        showAuthModal('setup');
    }
}

function showAuthModal(mode) {
    console.log('Showing auth modal in mode:', mode);
    const authModal = document.getElementById('auth-modal');
    const setupForm = document.getElementById('setup-form');
    const loginForm = document.getElementById('login-form');
    const authModalTitle = document.getElementById('auth-modal-title');
    const authSwitchText = document.getElementById('auth-switch-text');
    const authSwitchBtn = document.getElementById('auth-switch-btn');
    
    console.log('Auth modal element:', authModal);
    console.log('Setup form element:', setupForm);
    console.log('Login form element:', loginForm);
    
    if (!authModal) {
        console.error('Auth modal element not found!');
        return;
    }
    
    if (mode === 'setup') {
        setupForm.style.display = 'block';
        loginForm.style.display = 'none';
        authModalTitle.textContent = 'Welcome to Shakshuka';
        authSwitchText.textContent = 'Already have an account?';
        authSwitchBtn.textContent = 'Login';
    } else {
        setupForm.style.display = 'none';
        loginForm.style.display = 'block';
        authModalTitle.textContent = 'Login to Shakshuka';
        authSwitchText.textContent = "Don't have an account?";
        authSwitchBtn.textContent = 'Setup';
    }
    
    authModal.style.display = 'flex';
    authModal.style.position = 'fixed';
    authModal.style.top = '0';
    authModal.style.left = '0';
    authModal.style.width = '100%';
    authModal.style.height = '100%';
    authModal.style.zIndex = '9999';
    authModal.style.backgroundColor = 'rgba(0, 0, 0, 0.6)';
    authModal.style.alignItems = 'center';
    authModal.style.justifyContent = 'center';
    console.log('Auth modal displayed, style:', authModal.style.display);
}

function hideAuthModal() {
    const authModal = document.getElementById('auth-modal');
    authModal.style.display = 'none';
}

async function setupPassword() {
    const password = document.getElementById('setup-password').value.trim();
    const confirmPassword = document.getElementById('setup-confirm-password').value.trim();
    
    console.log('Setup Password Debug:');
    console.log('- Password element:', document.getElementById('setup-password'));
    console.log('- Confirm password element:', document.getElementById('setup-confirm-password'));
    console.log('- Password value:', password);
    console.log('- Confirm password value:', confirmPassword);
    console.log('- Password length:', password.length);
    console.log('- Confirm password length:', confirmPassword.length);
    console.log('- Passwords match:', password === confirmPassword);
    
    if (!password || !confirmPassword) {
        console.log('Validation failed: Empty fields');
        showNotification('Please fill in both password fields', 'error');
        return;
    }
    
    if (password !== confirmPassword) {
        showNotification('Passwords do not match', 'error');
        return;
    }
    
    if (password.length < 6) {
        showNotification('Password must be at least 6 characters', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/auth/setup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ password })
        });
        
        if (response.ok) {
            isAuthenticated = true;
            passwordSet = true;
            hideAuthModal();
            loadAppData();
            showNotification('Account setup successful!', 'success');
        } else {
            const error = await response.json();
            console.error('Setup error response:', error);
            showNotification(error.error || 'Setup failed', 'error');
        }
    } catch (error) {
        console.error('Setup error:', error);
        showNotification('Setup failed', 'error');
    }
}

async function login() {
    const password = document.getElementById('login-password').value;
    
    if (!password) {
        showNotification('Please enter your password', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ password })
        });
        
        if (response.ok) {
            isAuthenticated = true;
            passwordSet = true;
            hideAuthModal();
            loadAppData();
            showNotification('Login successful!', 'success');
        } else {
            const error = await response.json();
            showNotification(error.error || 'Login failed', 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showNotification('Login failed', 'error');
    }
}

async function logout() {
    try {
        const response = await fetch('/api/auth/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            isAuthenticated = false;
            passwordSet = false;
            showAuthModal('login');
            showNotification('Logged out successfully', 'success');
        } else {
            showNotification('Logout failed', 'error');
        }
    } catch (error) {
        console.error('Logout error:', error);
        showNotification('Logout failed', 'error');
    }
}

function loadAppData() {
    // Load all app data after authentication
    loadTasks();
    loadSettings();
    loadUpdateSettings();
    generateTimeSlots();
    applyThemeAndDPI();
    setupDailyReset();
    setupKeyboardShortcuts();
    initializeLogging();
}

function clearLogs() {
    developerLogs = [];
    displayLogs();
    addLog('info', 'Logs cleared');
}

// Initialize the application
function initializeApp() {
    updateDashboardStats();
    updateCurrentDate();
}

// Setup event listeners
function setupEventListeners() {
    // Authentication
    safeAddEventListener('setup-form', 'submit', (e) => {
        e.preventDefault();
        setupPassword();
    });
    
    safeAddEventListener('login-form', 'submit', (e) => {
        e.preventDefault();
        login();
    });
    
    safeAddEventListener('auth-switch-btn', 'click', () => {
        const setupForm = document.getElementById('setup-form');
        const loginForm = document.getElementById('login-form');
        
        if (setupForm.style.display === 'none') {
            showAuthModal('setup');
        } else {
            showAuthModal('login');
        }
    });
    
    safeAddEventListener('close-auth-modal', 'click', hideAuthModal);

    // Logout button
    const logoutBtn = document.getElementById('logout-btn');
    console.log('Logout button element:', logoutBtn);
    if (logoutBtn) {
        logoutBtn.addEventListener('click', logout);
        console.log('Logout button event listener added');
        
        // Make button more visible for testing
        logoutBtn.style.backgroundColor = '#ff4444';
        logoutBtn.style.color = 'white';
        logoutBtn.style.border = '2px solid #ff0000';
        console.log('Logout button styled for visibility');
    } else {
        console.error('Logout button not found!');
        
        // Try to find the settings page and add a logout button manually
        const settingsPage = document.getElementById('settings-page');
        if (settingsPage) {
            console.log('Settings page found, adding logout button manually');
            const accountSection = settingsPage.querySelector('.settings-section:last-child');
            if (accountSection) {
                const logoutBtn = document.createElement('button');
                logoutBtn.id = 'logout-btn';
                logoutBtn.className = 'btn-secondary';
                logoutBtn.innerHTML = '<i class="fas fa-sign-out-alt"></i> Logout';
                logoutBtn.style.backgroundColor = '#ff4444';
                logoutBtn.style.color = 'white';
                logoutBtn.addEventListener('click', logout);
                
                const settingItem = document.createElement('div');
                settingItem.className = 'setting-item';
                settingItem.appendChild(logoutBtn);
                accountSection.appendChild(settingItem);
                
                console.log('Logout button added manually');
            }
        }
    }

    // Navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', function() {
            const page = this.dataset.page;
            navigateToPage(page);
        });
    });

    // Task modals
    safeAddEventListener('add-task-btn-2', 'click', () => openTaskModal());
    safeAddEventListener('quick-add-btn', 'click', () => openQuickAddModal());
    
    // Modal controls
    safeAddEventListener('close-modal', 'click', () => closeTaskModal());
    safeAddEventListener('close-quick-modal', 'click', () => closeQuickAddModal());
    safeAddEventListener('cancel-task', 'click', () => closeTaskModal());
    safeAddEventListener('cancel-quick-task', 'click', () => closeQuickAddModal());
    
    // Form submissions
    safeAddEventListener('save-task', 'click', () => saveTask());
    safeAddEventListener('save-quick-task', 'click', () => saveQuickTask());
    
    // Filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const filter = this.dataset.filter;
            setActiveFilter(filter);
            filterTasks(filter);
        });
    });

    // Date navigation
    safeAddEventListener('prev-day', 'click', () => changeDate(-1));
    safeAddEventListener('next-day', 'click', () => changeDate(1));

    // Settings
    safeAddEventListener('autostart-toggle', 'change', updateAutostart);
    safeAddEventListener('autosave-interval', 'change', updateAutosaveInterval);
    safeAddEventListener('daily-reset-time', 'change', updateDailyResetTime);
    safeAddEventListener('theme-selector', 'change', updateTheme);
    safeAddEventListener('dpi-selector', 'change', updateDPI);
    safeAddEventListener('change-password-btn', 'click', openPasswordModal);
    safeAddEventListener('export-data-btn', 'click', exportData);
    safeAddEventListener('clear-data-btn', 'click', clearAllData);
    
    // Developer logs
    safeAddEventListener('view-logs-btn', 'click', openLogsModal);
    safeAddEventListener('close-logs-modal', 'click', closeLogsModal);
    safeAddEventListener('close-logs-btn', 'click', closeLogsModal);
    safeAddEventListener('clear-logs-btn', 'click', clearLogs);
    safeAddEventListener('refresh-logs-btn', 'click', displayLogs);
    
    // Strike modal
    safeAddEventListener('close-strike-modal', 'click', closeStrikeModal);
    safeAddEventListener('cancel-strike', 'click', closeStrikeModal);
    safeAddEventListener('strike-today-btn', 'click', strikeTaskToday);
    safeAddEventListener('strike-forever-btn', 'click', strikeTaskForever);

    // Schedule modal event listeners
    safeAddEventListener('add-task-to-planner', 'click', openScheduleModal);
    safeAddEventListener('close-schedule-modal', 'click', closeScheduleModal);
    safeAddEventListener('cancel-schedule', 'click', closeScheduleModal);
    safeAddEventListener('confirm-schedule', 'click', confirmSchedule);

    // Layout toggle
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const layout = this.dataset.layout;
            setLayout(layout);
        });
    });

    // Sidebar toggle
    safeAddEventListener('sidebar-toggle', 'click', toggleSidebar);

    // Password modal
    safeAddEventListener('close-password-modal', 'click', closePasswordModal);
    safeAddEventListener('cancel-password', 'click', closePasswordModal);
    safeAddEventListener('save-password', 'click', savePassword);

    // Update and backup modals
    safeAddEventListener('close-backup-modal', 'click', closeBackupModal);
    safeAddEventListener('cancel-backup', 'click', closeBackupModal);
    safeAddEventListener('create-new-backup', 'click', createBackup);
    safeAddEventListener('manage-backups-btn', 'click', openBackupModal);
    
    safeAddEventListener('close-update-modal', 'click', closeUpdateModal);
    safeAddEventListener('cancel-update', 'click', closeUpdateModal);
    safeAddEventListener('download-update', 'click', downloadAndInstallUpdate);
    
    // Update and backup buttons
    safeAddEventListener('check-updates-btn', 'click', checkForUpdates);
    safeAddEventListener('create-backup-btn', 'click', createBackup);
    
    // Update settings
    safeAddEventListener('auto-update-check', 'change', updateUpdateSettings);
    safeAddEventListener('auto-update-install', 'change', updateUpdateSettings);
    safeAddEventListener('backup-before-update', 'change', updateUpdateSettings);
    safeAddEventListener('update-channel', 'change', updateUpdateSettings);
    safeAddEventListener('check-interval', 'change', updateUpdateSettings);

    // Quick actions
    safeAddEventListener('focus-mode-btn', 'click', () => navigateToPage('planner'));
    safeAddEventListener('schedule-btn', 'click', () => navigateToPage('planner'));
    
    // Layout buttons
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const layout = btn.getAttribute('data-layout');
            console.log('Layout button clicked:', layout);
            setLayout(layout);
        });
    });

    // Close modals on outside click
    document.querySelectorAll('.modal').forEach(modal => {
        modal.addEventListener('click', function(e) {
            if (e.target === this) {
                this.classList.remove('active');
            }
        });
    });
}

// Navigation
function navigateToPage(page) {
    // Check authentication before navigating
    if (!isAuthenticated) {
        console.log('Not authenticated, showing login modal');
        showAuthModal('login');
        return;
    }
    
    // Update navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    document.querySelector(`[data-page="${page}"]`).classList.add('active');

    // Update pages
    document.querySelectorAll('.page').forEach(pageEl => {
        pageEl.classList.remove('active');
    });
    document.getElementById(`${page}-page`).classList.add('active');

    currentPage = page;

    // Load page-specific data
    if (page === 'tasks') {
        loadTasks();
    } else if (page === 'planner') {
        loadPlannerData();
    } else if (page === 'analytics') {
        updateDashboardStats();
    }
}

// Task Management
async function loadTasks() {
    try {
        showLoading(true);
        const response = await fetch('/api/tasks');
        
        if (!response.ok) {
            if (response.status === 401) {
                // Authentication required - show login modal
                console.log('Authentication required, showing login modal');
                showAuthModal('login');
                tasks = []; // Set empty array to prevent errors
                return;
            }
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        // Ensure tasks is always an array
        tasks = Array.isArray(data) ? data : [];
        
        if (currentPage === 'tasks') {
            renderTasks(currentFilter);
        } else if (currentPage === 'analytics') {
            renderRecentTasks();
        } else if (currentPage === 'planner') {
            loadScheduledTasks();
        }
        
        updateDashboardStats();
        addLog('success', `Loaded ${tasks.length} tasks`);
    } catch (error) {
        console.error('Error loading tasks:', error);
        addLog('error', `Failed to load tasks: ${error.message}`);
        
        // Check if it's an auth error
        if (error.message && error.message.toLowerCase().includes('login')) {
            showNotification('Please log in to access your tasks', 'error');
        } else {
            showNotification('Error loading tasks', 'error');
        }
        
        // Ensure tasks is always an array even on error
        tasks = [];
    } finally {
        showLoading(false);
    }
}

async function createTask(taskData) {
    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            const newTask = await response.json();
            tasks.push(newTask);
            updateDashboardStats();
            
            if (currentPage === 'tasks') {
                renderTasks();
            } else if (currentPage === 'dashboard') {
                renderRecentTasks();
            }
            
            showNotification('Task created successfully!', 'success');
            return newTask;
        } else {
            if (response.status === 401) {
                console.log('Authentication required for task creation');
                showAuthModal('login');
                throw new Error('Please log in to create tasks');
            } else {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Failed to create task (${response.status})`);
            }
        }
    } catch (error) {
        console.error('Error creating task:', error);
        showNotification(error.message || 'Error creating task', 'error');
    }
}

async function updateTask(taskId, taskData) {
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
            const index = tasks.findIndex(task => task.id === taskId);
            if (index !== -1) {
                tasks[index] = updatedTask;
            }
            
            updateDashboardStats();
            
            if (currentPage === 'tasks') {
                renderTasks();
            } else if (currentPage === 'dashboard') {
                renderRecentTasks();
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
    }
}

async function deleteTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            tasks = tasks.filter(task => task.id !== taskId);
            updateDashboardStats();
            
            if (currentPage === 'tasks') {
                renderTasks();
            } else if (currentPage === 'dashboard') {
                renderRecentTasks();
            }
            
            showNotification('Task deleted successfully!', 'success');
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
    }
}

async function completeTask(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });

        if (response.ok) {
            const completedTask = await response.json();
            const index = tasks.findIndex(task => task.id === taskId);
            if (index !== -1) {
                tasks[index] = completedTask;
            }
            
            updateDashboardStats();
            
            if (currentPage === 'tasks') {
                renderTasks();
            } else if (currentPage === 'dashboard') {
                renderRecentTasks();
            }
            
            showNotification('Task completed! 🎉', 'success');
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
    }
}

// Task Rendering
function renderTasks(filter = currentFilter) {
    const tasksList = document.getElementById('tasks-list');
    
    console.log('renderTasks called with:', {
        filter,
        currentLayout,
        tasksLength: tasks ? tasks.length : 'tasks is null/undefined',
        isAuthenticated,
        passwordSet
    });
    
    // Ensure tasks is an array before filtering
    if (!Array.isArray(tasks)) {
        console.warn('renderTasks: tasks is not an array:', tasks);
        tasks = [];
    }
    
    const filteredTasks = filterTasksByType(tasks, filter);
    console.log('Filtered tasks:', filteredTasks.length, filteredTasks);
    
    // Sort tasks: active tasks first, then struck tasks
    const sortedTasks = filteredTasks.sort((a, b) => {
        // If both are struck today, maintain original order
        if (a.struck_today && b.struck_today) return 0;
        // If only a is struck today, b comes first
        if (a.struck_today && !b.struck_today) return 1;
        // If only b is struck today, a comes first
        if (!a.struck_today && b.struck_today) return -1;
        // If neither are struck, maintain original order
        return 0;
    });
    
    if (sortedTasks.length === 0) {
        // Check if user is not authenticated
        if (!isAuthenticated) {
            tasksList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-lock" style="font-size: 3rem; color: #FFB6C1; margin-bottom: 1rem;"></i>
                    <h3>Authentication Required</h3>
                    <p>Please log in to view your tasks</p>
                    <button class="btn btn-primary" onclick="showAuthModal('login')">Login</button>
                </div>
            `;
        } else {
            tasksList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-tasks" style="font-size: 3rem; color: #FFB6C1; margin-bottom: 1rem;"></i>
                    <h3>No tasks found</h3>
                    <p>Create your first task to get started!</p>
                </div>
            `;
        }
        return;
    }

    if (currentLayout === 'grid') {
        console.log('Rendering grid layout with', sortedTasks.length, 'tasks');
        const gridHTML = `
            <div class="tasks-grid">
                ${sortedTasks.map(task => {
                    // Calculate progress based on strikes and completion
                    const maxStrikes = 8; // Maximum strikes before completion
                    const currentStrikes = task.strike_count || 0;
                    const progressPercentage = task.completed ? 100 : Math.min((currentStrikes / maxStrikes) * 100, 100);
                    const progressStep = task.completed ? maxStrikes : Math.min(currentStrikes + 1, maxStrikes);
                    
                    return `
                        <div class="task-card ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${task.strike_count > 1 ? 'restrike' : ''}" data-task-id="${task.id}" style="background: linear-gradient(135deg, #ff8c42 0%, #ffa726 50%, #ffffff 100%); border-radius: 20px; padding: 0; border: none; box-shadow: 0 8px 25px rgba(255, 140, 66, 0.2); overflow: hidden; position: relative; min-height: 200px;">
                            <div class="task-actions">
                                ${task.struck_today && !task.completed ? `
                                    <button class="task-action undo-action" onclick="undoStrike('${task.id}')" title="Undo Strike">
                                        <i class="fas fa-undo"></i>
                                    </button>
                                ` : ''}
                                ${!task.completed ? `
                                    <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                                        <i class="fas fa-check"></i>
                                    </button>
                                ` : ''}
                                <button class="task-action" onclick="editTask('${task.id}')" title="Edit">
                                    <i class="fas fa-edit"></i>
                                </button>
                                <button class="task-action" onclick="deleteTask('${task.id}')" title="Delete">
                                    <i class="fas fa-trash"></i>
                                </button>
                            </div>
                            
                            <div class="task-header">
                                <h3 class="task-title ${task.struck_today ? 'struck-today' : ''}">${task.title.toUpperCase()}</h3>
                                ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
                                ${task.project ? `<span class="task-project">${task.project}</span>` : ''}
                            </div>
                            
                            <div class="task-progress">
                                <div class="progress-text">STEP ${progressStep} OF ${maxStrikes}</div>
                                <div class="progress-bar">
                                    <div class="progress-fill" style="width: ${progressPercentage}%"></div>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
        console.log('Generated grid HTML:', gridHTML);
        tasksList.innerHTML = gridHTML;
    } else {
        tasksList.innerHTML = sortedTasks.map(task => `
        <div class="task-item ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${task.strike_count > 1 ? 'restrike' : ''}" data-task-id="${task.id}">
            <div class="task-header">
                <h3 class="task-title ${task.struck_today ? 'struck-today' : ''}">${task.title}</h3>
                ${task.project ? `<span class="task-project">${task.project}</span>` : ''}
            </div>
            ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
            ${task.strike_report ? `<p class="strike-report"><em>Last strike: ${task.strike_report}</em></p>` : ''}
            <div class="task-meta">
                <div class="task-actions">
                    ${task.struck_today && !task.completed ? `
                        <button class="task-action undo-action" onclick="undoStrike('${task.id}')" title="Undo Strike">
                            <i class="fas fa-undo"></i>
                        </button>
                    ` : ''}
                    ${!task.completed ? `
                        <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                            <i class="fas fa-check"></i>
                        </button>
                    ` : ''}
                    <button class="task-action" onclick="editTask('${task.id}')" title="Edit">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="task-action" onclick="deleteTask('${task.id}')" title="Delete">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
    }
}

function renderRecentTasks() {
    const recentTasksList = document.getElementById('recent-tasks-list');
    const recentTasks = tasks.slice(-5).reverse();
    
    if (recentTasks.length === 0) {
        recentTasksList.innerHTML = `
            <div class="empty-state">
                <p>No recent tasks</p>
            </div>
        `;
        return;
    }

    recentTasksList.innerHTML = recentTasks.map(task => `
        <div class="task-item ${task.completed ? 'completed' : ''}" data-task-id="${task.id}">
            <div class="task-header">
                <h4 class="task-title ${task.struck_today ? 'struck-today' : ''}">${task.title}</h4>
                ${task.project ? `<span class="task-project">${task.project}</span>` : ''}
            </div>
            <div class="task-meta">
                ${task.completed ? `
                    <button class="task-action" onclick="undoCompleteTask('${task.id}')" title="Undo">
                        <i class="fas fa-undo"></i>
                    </button>
                ` : `
                    <button class="task-action" onclick="completeTask('${task.id}')" title="Complete">
                        <i class="fas fa-check"></i>
                    </button>
                `}
            </div>
        </div>
    `).join('');
}

// Remove the old filterTasksByType function - it's duplicated below

function setActiveFilter(filter) {
    currentFilter = filter; // Update global filter
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-filter="${filter}"]`).classList.add('active');
}

function filterTasks(filter) {
    currentFilter = filter; // Update global filter
    renderTasks(filter);
}

// Dashboard Stats
function updateDashboardStats() {
    const completedToday = tasks.filter(task => {
        if (!task.completed || !task.completed_at) return false;
        const completedDate = new Date(task.completed_at);
        const today = new Date();
        return completedDate.toDateString() === today.toDateString();
    }).length;

    const pendingTasks = tasks.filter(task => !task.completed).length;
    
    // Calculate streak (simplified)
    const streakDays = calculateStreak();
    
    // Calculate productivity score
    const productivityScore = calculateProductivityScore();

    document.getElementById('completed-today').textContent = completedToday;
    document.getElementById('expired-tasks').textContent = pendingTasks;
    document.getElementById('streak-days').textContent = streakDays;
    document.getElementById('productivity-score').textContent = productivityScore + '%';
}

function calculateStreak() {
    // Simplified streak calculation
    const completedTasks = tasks.filter(task => task.completed);
    if (completedTasks.length === 0) return 0;
    
    // For demo purposes, return a random streak
    return Math.min(completedTasks.length, 30);
}

function calculateProductivityScore() {
    if (tasks.length === 0) return 0;
    
    const completedTasks = tasks.filter(task => task.completed).length;
    const totalTasks = tasks.length;
    
    return Math.round((completedTasks / totalTasks) * 100);
}

// Modal Functions
function openTaskModal(taskId = null) {
    editingTaskId = taskId;
    const modal = document.getElementById('task-modal');
    const title = document.getElementById('modal-title');
    
    if (taskId) {
        const task = tasks.find(t => t.id === taskId);
        if (task) {
            title.textContent = 'Edit Task';
            populateTaskForm(task);
        }
    } else {
        title.textContent = 'Add New Task';
        clearTaskForm();
    }
    
    modal.classList.add('active');
}

function closeTaskModal() {
    document.getElementById('task-modal').classList.remove('active');
    editingTaskId = null;
    clearTaskForm();
}

function openQuickAddModal() {
    document.getElementById('quick-add-modal').classList.add('active');
    document.getElementById('quick-task-title').focus();
}

function closeQuickAddModal() {
    document.getElementById('quick-add-modal').classList.remove('active');
    document.getElementById('quick-task-form').reset();
}

function editTask(taskId) {
    openTaskModal(taskId);
}

async function undoCompleteTask(taskId) {
    await updateTask(taskId, { completed: false, completed_at: null });
}

// Form Submissions
async function saveTask() {
    const form = document.getElementById('task-form');
    const formData = new FormData(form);
    
    const taskData = {
        title: document.getElementById('task-title').value,
        description: document.getElementById('task-description').value,
        priority: document.getElementById('task-priority').value,
        category: document.getElementById('task-category').value,
        due_date: document.getElementById('task-due-date').value,
        estimated_duration: parseInt(document.getElementById('task-duration').value)
    };

    if (!taskData.title.trim()) {
        showNotification('Please enter a task title', 'error');
        return;
    }

    try {
        if (editingTaskId) {
            await updateTask(editingTaskId, taskData);
        } else {
            await createTask(taskData);
        }
        
        closeTaskModal();
    } catch (error) {
        console.error('Error saving task:', error);
    }
}

async function saveQuickTask() {
    const title = document.getElementById('quick-task-title').value.trim();
    
    if (!title) {
        showNotification('Please enter a task title', 'error');
        return;
    }

    const taskData = {
        title: title,
        description: '',
        priority: 'medium',
        category: 'general',
        estimated_duration: 60
    };

    try {
        await createTask(taskData);
        closeQuickAddModal();
    } catch (error) {
        console.error('Error saving quick task:', error);
    }
}

// Planner Functions
function generateTimeSlots() {
    const timeGrid = document.querySelector('.time-grid');
    const hours = Array.from({ length: 24 }, (_, i) => i);
    
    timeGrid.innerHTML = hours.map(hour => `
        <div class="time-slot" data-hour="${hour}">
            <div class="time-label">${formatHour(hour)}</div>
            <div class="time-content" data-hour="${hour}">
                <!-- Scheduled tasks will be added here -->
            </div>
        </div>
    `).join('');
    
    setupDragAndDrop();
}

function formatHour(hour) {
    const period = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    return `${displayHour}:00 ${period}`;
}

function setupDragAndDrop() {
    console.log('Setting up drag and drop...');
    
    // Make tasks draggable
    const draggableTasks = document.querySelectorAll('.draggable-task');
    console.log('Found draggable tasks:', draggableTasks.length);
    
    draggableTasks.forEach(task => {
        task.draggable = true;
        task.addEventListener('dragstart', handleDragStart);
        task.addEventListener('dragend', handleDragEnd);
    });

    // Make time slots droppable
    const timeContents = document.querySelectorAll('.time-content');
    console.log('Found time slots:', timeContents.length);
    
    timeContents.forEach(slot => {
        slot.addEventListener('dragover', handleDragOver);
        slot.addEventListener('drop', handleDrop);
        slot.addEventListener('dragenter', handleDragEnter);
        slot.addEventListener('dragleave', handleDragLeave);
    });
    
    // Make scheduled tasks draggable again
    const scheduledTasks = document.querySelectorAll('.scheduled-task');
    console.log('Found scheduled tasks:', scheduledTasks.length);
    
    scheduledTasks.forEach(task => {
        task.draggable = true;
        task.addEventListener('dragstart', handleDragStart);
        task.addEventListener('dragend', handleDragEnd);
    });
}

function handleDragStart(e) {
    console.log('Drag started for task:', e.target.dataset.taskId);
    e.dataTransfer.setData('text/plain', e.target.dataset.taskId);
    e.target.style.opacity = '0.5';
}

function handleDragEnd(e) {
    console.log('Drag ended');
    e.target.style.opacity = '1';
}

function handleDragOver(e) {
    e.preventDefault();
}

function handleDragEnter(e) {
    console.log('Drag enter on hour:', e.target.dataset.hour);
    e.preventDefault();
    e.target.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.target.classList.remove('drag-over');
}

async function handleDrop(e) {
    console.log('Drop event triggered');
    e.preventDefault();
    e.target.classList.remove('drag-over');
    
    const taskId = e.dataTransfer.getData('text/plain');
    const hour = e.target.dataset.hour;
    
    console.log('Dropping task:', taskId, 'at hour:', hour);
    
    // Check if this is a scheduled task being moved
    const scheduledTask = document.querySelector(`.scheduled-task[data-task-id="${taskId}"]`);
    if (scheduledTask) {
        // Remove from current time slot
        scheduledTask.remove();
    }
    
    // Schedule task with default 30-minute duration
    try {
        const response = await fetch(`/api/tasks/${taskId}/schedule`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                hour: `${hour}:00`,
                duration: 30
            })
        });
        
        if (response.ok) {
            loadPlannerData(); // Refresh both available and scheduled tasks
            showNotification('Task scheduled! 📅', 'success');
        } else {
            throw new Error('Failed to schedule task');
        }
    } catch (error) {
        console.error('Error scheduling task:', error);
        showNotification('Error scheduling task', 'error');
    }
}

async function scheduleTask(taskId, hour) {
    const task = tasks.find(t => t.id === taskId);
    if (!task) return;

    const scheduledDate = currentDate.toISOString().split('T')[0];
    
    try {
        await updateTask(taskId, {
            scheduled_hour: `${hour}:00`,
            scheduled_date: scheduledDate
        });
        
        loadPlannerData();
        showNotification('Task scheduled successfully!', 'success');
    } catch (error) {
        console.error('Error scheduling task:', error);
        showNotification('Error scheduling task', 'error');
    }
}

function loadPlannerData() {
    generateTimeSlots(); // Initialize the time grid first
    loadAvailableTasks();
    loadScheduledTasks();
}

function loadAvailableTasks() {
    const availableTasks = document.getElementById('available-tasks');
    
    console.log('Loading available tasks...');
    console.log('Total tasks:', tasks.length);
    console.log('Tasks:', tasks);
    
    const unscheduledTasks = tasks.filter(task => {
        const isUnscheduled = !task.scheduled_hour;
        const isNotCompleted = !task.completed;
        console.log(`Task ${task.title}: scheduled_hour=${task.scheduled_hour}, completed=${task.completed}, unscheduled=${isUnscheduled}, notCompleted=${isNotCompleted}`);
        return isUnscheduled && isNotCompleted;
    });
    
    console.log('Unscheduled tasks:', unscheduledTasks);
    
    if (unscheduledTasks.length === 0) {
        availableTasks.innerHTML = '<p>No available tasks to schedule.</p>';
    } else {
        availableTasks.innerHTML = unscheduledTasks.map(task => `
            <div class="draggable-task" data-task-id="${task.id}">
                <h4>${task.title}</h4>
                <p>${task.project || 'No Project'} • ${task.estimated_duration || 30}min</p>
            </div>
        `).join('');
    }
    
    setupDragAndDrop();
}

function loadScheduledTasks() {
    const scheduledDate = currentDate.toISOString().split('T')[0];
    const scheduledTasks = tasks.filter(task => 
        task.scheduled_date === scheduledDate && task.scheduled_hour
    );
    
    // Clear existing scheduled tasks
    document.querySelectorAll('.scheduled-task').forEach(task => task.remove());
    
    // Add scheduled tasks to their time slots
    scheduledTasks.forEach(task => {
        const hour = parseInt(task.scheduled_hour.split(':')[0]);
        const timeContent = document.querySelector(`[data-hour="${hour}"]`);
        
        if (timeContent) {
            const scheduledTaskEl = document.createElement('div');
            scheduledTaskEl.className = 'scheduled-task';
            scheduledTaskEl.innerHTML = `
                <div class="scheduled-task-header">
                    <h4>${task.title}</h4>
                    <button class="remove-task-btn" onclick="unscheduleTask('${task.id}')" title="Remove from planner">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <p class="task-duration">${task.duration || 30} min</p>
                ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
            `;
            scheduledTaskEl.dataset.taskId = task.id;
            
            timeContent.appendChild(scheduledTaskEl);
        }
    });
    
    // Re-setup drag and drop for scheduled tasks
    setupDragAndDrop();
}

function changeDate(days) {
    currentDate.setDate(currentDate.getDate() + days);
    updateCurrentDate();
    loadPlannerData();
}

function updateCurrentDate() {
    const dateElement = document.getElementById('current-date');
    const today = new Date();
    const isToday = currentDate.toDateString() === today.toDateString();
    
    if (isToday) {
        dateElement.textContent = 'Today';
    } else {
        dateElement.textContent = currentDate.toLocaleDateString('en-US', {
            weekday: 'long',
            month: 'short',
            day: 'numeric'
        });
    }
}

// Settings Functions
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        currentSettings = await response.json();
        
        document.getElementById('autostart-toggle').checked = currentSettings.autostart || false;
        document.getElementById('autosave-interval').value = currentSettings.autosave_interval || 30;
        document.getElementById('theme-selector').value = currentSettings.theme || 'light';
        document.getElementById('dpi-selector').value = currentSettings.dpi_scale || 100;
        
        applyThemeAndDPI();
    } catch (error) {
        console.error('Error loading settings:', error);
    }
}

async function updateAutostart() {
    const enabled = document.getElementById('autostart-toggle').checked;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ autostart: enabled })
        });

        if (response.ok) {
            showNotification(
                enabled ? 'Autostart enabled' : 'Autostart disabled', 
                'success'
            );
        } else {
            throw new Error('Failed to update autostart setting');
        }
    } catch (error) {
        console.error('Error updating autostart:', error);
        showNotification('Error updating autostart setting', 'error');
    }
}

async function updateAutosaveInterval() {
    const interval = parseInt(document.getElementById('autosave-interval').value);
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ autosave_interval: interval })
        });

        if (response.ok) {
            showNotification('Auto-save interval updated', 'success');
        } else {
            throw new Error('Failed to update autosave interval');
        }
    } catch (error) {
        console.error('Error updating autosave interval:', error);
        showNotification('Error updating auto-save interval', 'error');
    }
}

function exportData() {
    const data = {
        tasks: tasks,
        exportDate: new Date().toISOString(),
        version: '1.0'
    };
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement('a');
    a.href = url;
    a.download = `task-manager-backup-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showNotification('Data exported successfully!', 'success');
}

async function clearAllData() {
    if (!confirm('Are you sure you want to clear all data? This action cannot be undone.')) {
        return;
    }
    
    try {
        // Delete all tasks
        for (const task of tasks) {
            await fetch(`/api/tasks/${task.id}`, { method: 'DELETE' });
        }
        
        tasks = [];
        updateDashboardStats();
        
        if (currentPage === 'tasks') {
            renderTasks(currentFilter);
        } else if (currentPage === 'dashboard') {
            renderRecentTasks();
        }
        
        showNotification('All data cleared successfully!', 'success');
    } catch (error) {
        console.error('Error clearing data:', error);
        showNotification('Error clearing data', 'error');
    }
}

// Theme and DPI Functions
function applyThemeAndDPI() {
    const theme = currentSettings.theme || 'light';
    const dpiScale = currentSettings.dpi_scale || 100;
    
    // Apply theme
    document.body.setAttribute('data-theme', theme);
    
    // Apply DPI scaling (convert percentage to decimal)
    document.documentElement.style.setProperty('--dpi-scale', (dpiScale / 100));
}

async function updateTheme() {
    const theme = document.getElementById('theme-selector').value;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ theme: theme })
        });

        if (response.ok) {
            currentSettings.theme = theme;
            applyThemeAndDPI();
            showNotification('Theme updated successfully!', 'success');
        } else {
            throw new Error('Failed to update theme');
        }
    } catch (error) {
        console.error('Error updating theme:', error);
        showNotification('Error updating theme', 'error');
    }
}

async function updateDPI() {
    const dpiScale = parseInt(document.getElementById('dpi-selector').value);
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ dpi_scale: dpiScale })
        });

        if (response.ok) {
            currentSettings.dpi_scale = dpiScale;
            applyThemeAndDPI();
            showNotification('DPI scale updated successfully!', 'success');
        } else {
            throw new Error('Failed to update DPI scale');
        }
    } catch (error) {
        console.error('Error updating DPI scale:', error);
        showNotification('Error updating DPI scale', 'error');
    }
}

// Password Management Functions
function openPasswordModal() {
    document.getElementById('password-modal').classList.add('active');
    document.getElementById('current-password').focus();
}

function closePasswordModal() {
    document.getElementById('password-modal').classList.remove('active');
    document.getElementById('password-form').reset();
}

// Developer Logs Modal Functions
function openLogsModal() {
    document.getElementById('logs-modal').classList.add('active');
    displayLogs();
    addLog('info', 'Developer logs modal opened');
}

function closeLogsModal() {
    document.getElementById('logs-modal').classList.remove('active');
}

// Strike Modal Functions
let currentStrikeTaskId = null;

function openStrikeModal(taskId) {
    console.log('Opening strike modal for task:', taskId);
    currentStrikeTaskId = taskId;
    // Clear the report field
    document.getElementById('strike-report').value = '';
    document.getElementById('strike-modal').classList.add('active');
    document.getElementById('strike-report').focus();
    addLog('info', `Opening strike modal for task ${taskId}`);
}

function closeStrikeModal() {
    document.getElementById('strike-modal').classList.remove('active');
    document.getElementById('strike-report').value = '';
    currentStrikeTaskId = null;
}

async function strikeTaskToday() {
    const report = document.getElementById('strike-report').value.trim();
    if (!report) {
        showNotification('Please describe what you accomplished', 'error');
        return;
    }
    
    if (!currentStrikeTaskId) {
        showNotification('No task selected', 'error');
        return;
    }
    
    try {
        console.log('Attempting to strike task:', currentStrikeTaskId, 'with report:', report);
        
        const response = await fetch(`/api/tasks/${currentStrikeTaskId}/strike`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: 'today',
                report: report
            })
        });
        
        console.log('Strike response status:', response.status);
        
        if (response.ok) {
            closeStrikeModal();
            await loadTasks();
            updateDashboardStats();
            showNotification('Task struck for today! 📝', 'success');
            addLog('success', `Task ${currentStrikeTaskId} struck for today: ${report}`);
        } else {
            const errorData = await response.json();
            console.error('Strike error response:', errorData);
            throw new Error(errorData.error || 'Failed to strike task');
        }
    } catch (error) {
        console.error('Error striking task:', error);
        addLog('error', `Failed to strike task ${currentStrikeTaskId}: ${error.message}`);
        showNotification(`Error striking task: ${error.message}`, 'error');
    }
}

async function strikeTaskForever() {
    const report = document.getElementById('strike-report').value.trim();
    if (!report) {
        showNotification('Please describe what you accomplished', 'error');
        return;
    }
    
    if (!currentStrikeTaskId) {
        showNotification('No task selected', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${currentStrikeTaskId}/strike`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: 'forever',
                report: report
            })
        });
        
        if (response.ok) {
            closeStrikeModal();
            await loadTasks();
            updateDashboardStats();
            showNotification('Task completed forever! 🎉', 'success');
            addLog('success', `Task ${currentStrikeTaskId} struck forever: ${report}`);
        } else {
            throw new Error('Failed to strike task');
        }
    } catch (error) {
        console.error('Error striking task:', error);
        addLog('error', `Failed to strike task ${currentStrikeTaskId}: ${error.message}`);
        showNotification('Error striking task', 'error');
    }
}

async function undoStrike(taskId) {
    if (!confirm('Are you sure you want to undo this strike?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/undo-strike`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            await loadTasks();
            updateDashboardStats();
            showNotification('Strike undone successfully! ↩️', 'success');
            addLog('success', `Task ${taskId} strike undone`);
        } else {
            throw new Error('Failed to undo strike');
        }
    } catch (error) {
        console.error('Error undoing strike:', error);
        addLog('error', `Failed to undo strike for task ${taskId}: ${error.message}`);
        showNotification('Error undoing strike', 'error');
    }
}

// Schedule Modal Functions
let currentScheduleTaskId = null;

function openScheduleModal() {
    // Get available tasks (not scheduled)
    const availableTasks = tasks.filter(task => !task.completed && !task.scheduled_hour);
    
    if (availableTasks.length === 0) {
        showNotification('No available tasks to schedule', 'info');
        return;
    }
    
    // Create task selection dropdown
    const taskSelect = document.createElement('select');
    taskSelect.id = 'schedule-task-select';
    taskSelect.innerHTML = '<option value="">Select a task</option>' + 
        availableTasks.map(task => `<option value="${task.id}">${task.title}</option>`).join('');
    
    // Add to modal
    const formGroup = document.createElement('div');
    formGroup.className = 'form-group';
    formGroup.innerHTML = '<label for="schedule-task-select">Task:</label>';
    formGroup.appendChild(taskSelect);
    
    // Insert at the beginning of the form
    const form = document.getElementById('schedule-form');
    form.insertBefore(formGroup, form.firstChild);
    
    document.getElementById('schedule-modal').classList.add('active');
}

function closeScheduleModal() {
    document.getElementById('schedule-modal').classList.remove('active');
    // Clear form
    document.getElementById('schedule-hour').value = '';
    document.getElementById('schedule-duration').value = '30';
    // Remove task select if it exists
    const taskSelect = document.getElementById('schedule-task-select');
    if (taskSelect) {
        taskSelect.parentElement.remove();
    }
    currentScheduleTaskId = null;
}

async function confirmSchedule() {
    const taskId = document.getElementById('schedule-task-select').value;
    const hour = document.getElementById('schedule-hour').value;
    const duration = document.getElementById('schedule-duration').value;
    
    if (!taskId || !hour || !duration) {
        showNotification('Please fill in all fields', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/schedule`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                hour: hour,
                duration: parseInt(duration)
            })
        });
        
        if (response.ok) {
            closeScheduleModal();
            loadScheduledTasks();
            showNotification('Task scheduled successfully! 📅', 'success');
            addLog('success', `Task ${taskId} scheduled for ${hour} (${duration} min)`);
        } else {
            throw new Error('Failed to schedule task');
        }
    } catch (error) {
        console.error('Error scheduling task:', error);
        addLog('error', `Failed to schedule task ${taskId}: ${error.message}`);
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
            loadScheduledTasks();
            showNotification('Task removed from planner! ↩️', 'success');
            addLog('success', `Task ${taskId} unscheduled`);
        } else {
            throw new Error('Failed to unschedule task');
        }
    } catch (error) {
        console.error('Error unscheduling task:', error);
        addLog('error', `Failed to unschedule task ${taskId}: ${error.message}`);
        showNotification('Error removing task from planner', 'error');
    }
}

async function savePassword() {
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (!currentPassword || !newPassword || !confirmPassword) {
        showNotification('Please fill in all password fields', 'error');
        return;
    }
    
    if (newPassword.length < 6) {
        showNotification('New password must be at least 6 characters long', 'error');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        showNotification('New passwords do not match', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/settings/password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        if (response.ok) {
            showNotification('Password changed successfully!', 'success');
            closePasswordModal();
        } else {
            const error = await response.json();
            showNotification(error.error || 'Failed to change password', 'error');
        }
    } catch (error) {
        console.error('Error changing password:', error);
        showNotification('Error changing password', 'error');
    }
}

// Utility Functions
function showLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (show) {
        overlay.classList.add('active');
    } else {
        overlay.classList.remove('active');
    }
}

function showNotification(message, type = 'info', options = {}) {
    // Check if this is an authentication-related error
    const isAuthError = type === 'error' && (
        message.toLowerCase().includes('login') || 
        message.toLowerCase().includes('authentication') ||
        message.toLowerCase().includes('access') ||
        message.toLowerCase().includes('unauthorized')
    );
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    // Make auth error notifications clickable
    if (isAuthError) {
        notification.style.cursor = 'pointer';
        notification.title = 'Click to open login dialog';
    }
    
    notification.innerHTML = `
        <div class="notification-content">
            <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'}"></i>
            <span>${message}</span>
            ${isAuthError ? '<span class="notification-hint">(Click to login)</span>' : ''}
            <button class="notification-close" onclick="closeNotification(this)">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'linear-gradient(135deg, #28A745, #20C997)' : 
                    type === 'error' ? 'linear-gradient(135deg, #DC3545, #E74C3C)' : 
                    'linear-gradient(135deg, #17A2B8, #20C997)'};
        color: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
        z-index: 4000;
        animation: slideInRight 0.3s ease-in-out;
        max-width: 400px;
        ${isAuthError ? 'border: 2px solid rgba(255, 255, 255, 0.3);' : ''}
    `;
    
    // Add click handler for auth errors
    if (isAuthError) {
        notification.addEventListener('click', (e) => {
            // Don't trigger if clicking the close button
            if (!e.target.closest('.notification-close')) {
                console.log('Auth error notification clicked, opening login dialog');
                showAuthModal('login');
                closeNotification(notification.querySelector('.notification-close'));
            }
        });
    }
    
    document.body.appendChild(notification);
    
    // Auto-open login dialog for auth errors
    if (isAuthError && options.autoOpenLogin !== false) {
        console.log('Auto-opening login dialog for auth error');
        setTimeout(() => {
            showAuthModal('login');
        }, 1000); // Small delay to let user see the notification first
    }
    
    // Remove after 5 seconds (increased from 3 to give time to close)
    setTimeout(() => {
        if (notification.parentNode) {
            notification.style.animation = 'slideOutRight 0.3s ease-in-out';
            setTimeout(() => {
                if (notification.parentNode) {
                    notification.parentNode.removeChild(notification);
                }
            }, 300);
        }
    }, 5000);
}

function closeNotification(closeButton) {
    const notification = closeButton.closest('.notification');
    if (notification) {
        notification.style.animation = 'slideOutRight 0.3s ease-in-out';
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }
}

// Add CSS for notifications
const notificationStyles = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    
    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
    
    .notification-content {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
`;

// Inject notification styles
const styleSheet = document.createElement('style');
styleSheet.textContent = notificationStyles;
document.head.appendChild(styleSheet);

// New Functions for Shakshuka Features

// Daily Reset Functionality
function setupDailyReset() {
    const resetTime = currentSettings.daily_reset_time || '09:00';
    scheduleDailyReset(resetTime);
}

function scheduleDailyReset(resetTime) {
    if (dailyResetTimer) {
        clearTimeout(dailyResetTimer);
    }
    
    const [hours, minutes] = resetTime.split(':').map(Number);
    const now = new Date();
    const resetDate = new Date();
    resetDate.setHours(hours, minutes, 0, 0);
    
    // If reset time has passed today, schedule for tomorrow
    if (resetDate <= now) {
        resetDate.setDate(resetDate.getDate() + 1);
    }
    
    const timeUntilReset = resetDate.getTime() - now.getTime();
    
    dailyResetTimer = setTimeout(() => {
        resetDailyStrikes();
        scheduleDailyReset(resetTime); // Schedule next reset
    }, timeUntilReset);
}

async function resetDailyStrikes() {
    try {
        const response = await fetch('/api/tasks/reset-daily-strikes', {
            method: 'POST'
        });
        
        if (response.ok) {
            await loadTasks(); // Reload tasks to reflect changes
            showNotification('Daily strikes reset!', 'success');
        }
    } catch (error) {
        console.error('Error resetting daily strikes:', error);
    }
}

// Layout Functions
function setLayout(layout) {
    currentLayout = layout;
    
    // Update active button
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-layout="${layout}"]`).classList.add('active');
    
    // Re-render tasks with new layout
    if (currentPage === 'tasks') {
        renderTasks();
    }
}

// Sidebar Functions
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    
    sidebar.classList.toggle('open');
    mainContent.classList.toggle('sidebar-collapsed');
}

// Keyboard Shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        // N key for new task (only when not typing in input fields)
        if ((e.key === 'n' || e.key === 'N') && !isTypingInInput(e.target)) {
            e.preventDefault();
            openTaskModal();
        }
        
        // Enter to save task, Ctrl+Enter for new line
        if (e.target.id === 'task-title' || e.target.id === 'task-description') {
            if (e.key === 'Enter' && !e.ctrlKey) {
                e.preventDefault();
                saveTask();
            }
        }
    });
}

function isTypingInInput(target) {
    // Check if the target is an input field, textarea, or contenteditable
    const inputTypes = ['input', 'textarea', 'select'];
    const isInput = inputTypes.includes(target.tagName.toLowerCase());
    const isContentEditable = target.contentEditable === 'true';
    const isInModal = target.closest('.modal') !== null;
    
    return isInput || isContentEditable || isInModal;
}

// Update and Backup Management Functions
let currentUpdateInfo = null;

async function checkForUpdates() {
    try {
        showNotification('Checking for updates...', 'info');
        
        const response = await fetch('/api/updates/check', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        const result = await response.json();
        
        if (result.update_available) {
            currentUpdateInfo = result.update_info;
            showUpdateModal(result.update_info);
            showNotification('Update available!', 'success');
        } else {
            showNotification('You are up to date!', 'success');
        }
    } catch (error) {
        console.error('Error checking for updates:', error);
        showNotification('Error checking for updates', 'error');
    }
}

function showUpdateModal(updateInfo) {
    const modal = document.getElementById('update-modal');
    const updateInfoDiv = document.getElementById('update-info');
    
    updateInfoDiv.innerHTML = `
        <div class="update-version">Version ${updateInfo.version}</div>
        <div class="update-notes">${updateInfo.release_notes || 'No release notes available.'}</div>
        <p><strong>Published:</strong> ${new Date(updateInfo.published_at).toLocaleDateString()}</p>
        ${updateInfo.prerelease ? '<p><strong>Note:</strong> This is a pre-release version.</p>' : ''}
    `;
    
    modal.classList.add('active');
}

function closeUpdateModal() {
    document.getElementById('update-modal').classList.remove('active');
    currentUpdateInfo = null;
}

async function downloadAndInstallUpdate() {
    if (!currentUpdateInfo) return;
    
    try {
        const progressDiv = document.getElementById('update-progress');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        
        // Show progress
        progressDiv.style.display = 'block';
        progressText.textContent = 'Downloading update...';
        
        // Download update
        const response = await fetch('/api/updates/download', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(currentUpdateInfo)
        });
        
        if (!response.ok) {
            throw new Error('Failed to download update');
        }
        
        progressText.textContent = 'Installing update...';
        progressFill.style.width = '100%';
        
        // Install update
        const installResponse = await fetch('/api/updates/install', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                update_file: `update_${currentUpdateInfo.version}.zip`,
                backup_before_update: true
            })
        });
        
        if (!installResponse.ok) {
            throw new Error('Failed to install update');
        }
        
        showNotification('Update installed successfully! Please restart the application.', 'success');
        closeUpdateModal();
        
    } catch (error) {
        console.error('Error updating:', error);
        showNotification('Error updating application', 'error');
    }
}

async function createBackup() {
    try {
        showNotification('Creating backup...', 'info');
        
        const response = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ type: 'manual' })
        });
        
        if (response.ok) {
            showNotification('Backup created successfully!', 'success');
        } else {
            throw new Error('Failed to create backup');
        }
    } catch (error) {
        console.error('Error creating backup:', error);
        showNotification('Error creating backup', 'error');
    }
}

async function openBackupModal() {
    try {
        const response = await fetch('/api/backups');
        const result = await response.json();
        
        const backupList = document.getElementById('backup-list');
        backupList.innerHTML = '';
        
        if (result.backups.length === 0) {
            backupList.innerHTML = '<p>No backups available.</p>';
        } else {
            result.backups.forEach(backup => {
                const backupItem = document.createElement('div');
                backupItem.className = 'backup-item';
                backupItem.innerHTML = `
                    <div class="backup-info">
                        <div class="backup-name">${backup.name}</div>
                        <div class="backup-details">
                            Type: ${backup.type} | 
                            Version: ${backup.version} | 
                            Created: ${new Date(backup.created_at).toLocaleString()}
                        </div>
                    </div>
                    <div class="backup-actions">
                        <button class="backup-action backup-restore" onclick="restoreBackup('${backup.name}')">
                            Restore
                        </button>
                    </div>
                `;
                backupList.appendChild(backupItem);
            });
        }
        
        document.getElementById('backup-modal').classList.add('active');
    } catch (error) {
        console.error('Error loading backups:', error);
        showNotification('Error loading backups', 'error');
    }
}

function closeBackupModal() {
    document.getElementById('backup-modal').classList.remove('active');
}

async function restoreBackup(backupName) {
    if (!confirm(`Are you sure you want to restore backup "${backupName}"? This will replace your current data.`)) {
        return;
    }
    
    try {
        showNotification('Restoring backup...', 'info');
        
        const response = await fetch('/api/backups/restore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ backup_name: backupName })
        });
        
        if (response.ok) {
            showNotification('Backup restored successfully! Please refresh the page.', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            throw new Error('Failed to restore backup');
        }
    } catch (error) {
        console.error('Error restoring backup:', error);
        showNotification('Error restoring backup', 'error');
    }
}

async function updateUpdateSettings() {
    try {
        const settings = {
            auto_check_enabled: document.getElementById('auto-update-check').checked,
            auto_install_enabled: document.getElementById('auto-update-install').checked,
            backup_before_update: document.getElementById('backup-before-update').checked,
            update_channel: document.getElementById('update-channel').value,
            check_interval_hours: parseInt(document.getElementById('check-interval').value)
        };
        
        const response = await fetch('/api/updates/config', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });
        
        if (response.ok) {
            showNotification('Update settings saved!', 'success');
        } else {
            throw new Error('Failed to save settings');
        }
    } catch (error) {
        console.error('Error updating settings:', error);
        showNotification('Error saving update settings', 'error');
    }
}

async function loadUpdateSettings() {
    try {
        const response = await fetch('/api/updates/config');
        const config = await response.json();
        
        document.getElementById('auto-update-check').checked = config.auto_check_enabled || false;
        document.getElementById('auto-update-install').checked = config.auto_install_enabled || false;
        document.getElementById('backup-before-update').checked = config.backup_before_update !== false;
        document.getElementById('update-channel').value = config.update_channel || 'stable';
        document.getElementById('check-interval').value = config.check_interval_hours || 24;
    } catch (error) {
        console.error('Error loading update settings:', error);
    }
}

// Update Settings Functions
async function updateDailyResetTime() {
    const resetTime = document.getElementById('daily-reset-time').value;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ daily_reset_time: resetTime })
        });

        if (response.ok) {
            currentSettings.daily_reset_time = resetTime;
            setupDailyReset(); // Reschedule with new time
            showNotification('Daily reset time updated!', 'success');
        } else {
            throw new Error('Failed to update daily reset time');
        }
    } catch (error) {
        console.error('Error updating daily reset time:', error);
        showNotification('Error updating daily reset time', 'error');
    }
}

// Update task rendering to use project instead of priority/category
// Update filter function
function filterTasksByType(tasks, filter) {
    // Ensure tasks is always an array
    if (!Array.isArray(tasks)) {
        console.warn('filterTasksByType received non-array tasks:', tasks);
        return [];
    }
    
    switch (filter) {
        case 'active':
            return tasks.filter(task => !task.completed);
        case 'completed':
            return tasks.filter(task => task.completed);
        case 'expired':
            const today = new Date().toISOString().split('T')[0];
            return tasks.filter(task => !task.completed && task.due_date && task.due_date < today);
        default:
            return tasks;
    }
}

// Update form handling
function populateTaskForm(task) {
    document.getElementById('task-title').value = task.title;
    document.getElementById('task-description').value = task.description || '';
    document.getElementById('task-project').value = task.project || '';
    document.getElementById('task-due-date').value = task.due_date || '';
    document.getElementById('task-duration').value = task.estimated_duration || 60;
}

function clearTaskForm() {
    document.getElementById('task-form').reset();
    document.getElementById('task-duration').value = 60;
}

async function saveTask() {
    const form = document.getElementById('task-form');
    
    const taskData = {
        title: document.getElementById('task-title').value,
        description: document.getElementById('task-description').value,
        project: document.getElementById('task-project').value,
        due_date: document.getElementById('task-due-date').value,
        estimated_duration: parseInt(document.getElementById('task-duration').value)
    };

    if (!taskData.title.trim()) {
        showNotification('Please enter a task title', 'error');
        return;
    }

    try {
        if (editingTaskId) {
            await updateTask(editingTaskId, taskData);
        } else {
            await createTask(taskData);
        }
        
        closeTaskModal();
    } catch (error) {
        console.error('Error saving task:', error);
    }
}

async function saveQuickTask() {
    const title = document.getElementById('quick-task-title').value.trim();
    
    if (!title) {
        showNotification('Please enter a task title', 'error');
        return;
    }

    const taskData = {
        title: title,
        description: '',
        project: '',
        estimated_duration: 60
    };

    try {
        await createTask(taskData);
        closeQuickAddModal();
    } catch (error) {
        console.error('Error saving quick task:', error);
    }
}
