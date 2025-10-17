// State Management Module
const AppState = (() => {
    const state = {
        currentPage: 'tasks',
        tasks: [],
        currentDate: new Date(),
        editingTaskId: null,
        currentSettings: {},
        currentLayout: 'list',
        dailyResetTimer: null,
        developerLogs: [],
        currentFilter: 'active',
        isAuthenticated: false,
        user: null,
        sessionId: null
    };

    return {
        get: (key) => state[key],
        set: (key, value) => { state[key] = value; },
        getAll: () => ({ ...state }),
        getTasks: () => [...state.tasks],
        setTasks: (tasks) => { state.tasks = tasks; },
        addTask: (task) => { state.tasks.push(task); },
        updateTask: (taskId, updatedTask) => {
            const index = state.tasks.findIndex(task => task.id === taskId);
            if (index !== -1) {
                state.tasks[index] = updatedTask;
            }
        },
        removeTask: (taskId) => {
            state.tasks = state.tasks.filter(task => task.id !== taskId);
        }
    };
})();

// Global functions that use AppState - no global variables needed

// Global CSRF token cache
let csrfToken = null;

// Helper function to get CSRF token
async function getCSRFToken() {
    if (!csrfToken) {
        try {
            const response = await fetch('/api/csrf-token');
            const data = await response.json();
            csrfToken = data.csrf_token;
        } catch (error) {
            console.error('Failed to get CSRF token:', error);
            csrfToken = null;
        }
    }
    return csrfToken;
}

// Helper function to make authenticated requests with CSRF token
async function makeAuthenticatedRequest(url, options = {}) {
    const token = await getCSRFToken();
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'X-CSRF-Token': token })
        }
    };
    
    return fetch(url, { ...defaultOptions, ...options });
}

// Helper function to safely add event listeners
function safeAddEventListener(elementId, event, handler) {
    const element = document.getElementById(elementId);
    if (element) {
        element.addEventListener(event, handler);
    } else {
        // Only log if it's not a password-related element (since password functionality was removed)
        if (!elementId.includes('password') && !elementId.includes('Password')) {
            console.warn(`Element with ID '${elementId}' not found, skipping event listener`);
        }
    }
}

// Safe error notification function
function safeShowNotification(message, type = 'info') {
    try {
        // Try to show notification if function exists
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            // Fallback to console and alert
            console.error('Error:', message);
            if (type === 'error') {
                alert('Error: ' + message);
            }
        }
    } catch (e) {
        console.error('Error in safeShowNotification:', e);
        console.error('Original error:', message);
    }
}

// Global error boundary
window.addEventListener('error', function(event) {
    console.error('Global error caught:', event.error);
    safeShowNotification('An unexpected error occurred. Please refresh the page.', 'error');

    // Log to developer console if available and AppState is initialized
    try {
        if (AppState && AppState.get && AppState.get('developerLogs')) {
            AppState.get('developerLogs').push({
                type: 'error',
                message: event.error.message,
                stack: event.error.stack,
                timestamp: new Date().toISOString()
            });
        }
    } catch (e) {
        console.error('Error logging to developer logs:', e);
    }
});

window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    safeShowNotification('A network error occurred. Please check your connection.', 'error');
    
    // Log to developer console if available and AppState is initialized
    try {
        if (AppState && AppState.get && AppState.get('developerLogs')) {
            AppState.get('developerLogs').push({
                type: 'error',
                message: `Promise rejection: ${event.reason}`,
                stack: event.reason?.stack || 'No stack trace',
                timestamp: new Date().toISOString()
            });
        }
    } catch (e) {
        console.error('Error logging promise rejection:', e);
    }
});

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    initializeApp();
    setupEventListeners();
    checkAuthStatus();
});

// Custom Logger (don't override console)
const Logger = {
    log: (...args) => {
        console.log(...args);
        addLog('info', args.join(' '));
    },
    error: (...args) => {
        console.error(...args);
        addLog('error', args.join(' '));
    },
    warn: (...args) => {
        console.warn(...args);
        addLog('warning', args.join(' '));
    },
    info: (...args) => {
        console.info(...args);
        addLog('info', args.join(' '));
    }
};

function initializeLogging() {
    // Don't override console methods anymore
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
    
    AppState.get('developerLogs').push(logEntry);
    
    // Keep only last 100 logs to prevent memory issues
    const logs = AppState.get('developerLogs');
    if (logs.length > 100) {
        AppState.set('developerLogs', logs.slice(-100));
    }
}

// XSS Protection - Sanitize HTML
function sanitizeHTML(str) {
    if (!str) return '';
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}

function displayLogs() {
    const logsContent = document.getElementById('logs-content');
    if (!logsContent) return;

    const logs = AppState.get('developerLogs');
    if (logs.length === 0) {
        logsContent.textContent = 'No logs available';
        return;
    }

    const logsHtml = logs.map(log => {
        return `<div class="log-entry ${log.level}">
            <div class="log-timestamp">[${log.timestamp}]</div>
            <div class="log-message">${log.message}</div>
        </div>`;
    }).join('');

    logsContent.innerHTML = logsHtml;
}

// Authentication Functions - DISABLED (no authentication needed)
async function checkAuthStatus() {
    // Skip authentication checks - always authenticated
    console.log('Authentication disabled - skipping auth checks');
    AppState.set('isAuthenticated', true);
    AppState.set('passwordSet', true);
    
    // Load app data directly
    console.log('Loading app data directly');
    loadAppData();
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
        
        // Auto-fill password if remembered
        const savedPassword = localStorage.getItem('shakshuka_password');
        if (savedPassword) {
            const passwordInput = document.getElementById('login-password');
            const rememberCheckbox = document.getElementById('remember-password');
            if (passwordInput) {
                passwordInput.value = savedPassword;
            }
            if (rememberCheckbox) {
                rememberCheckbox.checked = true;
            }
        }
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
            AppState.set('isAuthenticated', true);
            AppState.set('passwordSet', true);
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
    const rememberPassword = document.getElementById('remember-password')?.checked || false;
    
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
            AppState.set('isAuthenticated', true);
            AppState.set('passwordSet', true);
            
            // Remember password if checkbox is checked
            if (rememberPassword) {
                localStorage.setItem('shakshuka_password', password);
            } else {
                localStorage.removeItem('shakshuka_password');
            }
            
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

// Logout functionality removed - no authentication needed

function loadAppData() {
    console.log('loadAppData called');
    // Load all app data after authentication
    loadTasks();
    loadSettings();
    loadUpdateSettings();
    generateTimeSlots();
    applyThemeAndDPI();
    setupDailyReset();
    setupKeyboardShortcuts();
    initializeLogging();
    
    // If we're on the planner page, make sure it's loaded
    const currentPage = AppState.get('currentPage');
    console.log('Current page after loadAppData:', currentPage);
    if (currentPage === 'planner') {
        console.log('Loading planner data after app data load');
        loadPlannerData();
    }
}

function clearLogs() {
    AppState.set('developerLogs', []);
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
    // Authentication is disabled - no auth elements needed
    
    // Task form submission handler
    safeAddEventListener('task-form', 'submit', (e) => {
        e.preventDefault();
        saveTask();
    });
    
    // Quick task form submission handler
    safeAddEventListener('quick-task-form', 'submit', (e) => {
        e.preventDefault();
        saveQuickTask();
    });

    // Logout functionality removed - no authentication needed

    // Navigation
    console.log('Setting up navigation event listeners...');
    document.querySelectorAll('.nav-item').forEach(item => {
        console.log('Adding click listener to nav item:', item);
        item.addEventListener('click', function() {
            console.log('Nav item clicked:', this);
            const page = this.dataset.page;
            console.log('Navigating to page:', page);
            navigateToPage(page);
        });
    });
    console.log('Navigation event listeners set up complete');

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
    safeAddEventListener('finish-selector', 'change', updateFinish);
    safeAddEventListener('intensity-selector', 'change', updateIntensity);
    safeAddEventListener('dpi-selector', 'change', updateDPI);
    // Password change removed - no authentication needed
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
    
    // Account settings
    safeAddEventListener('change-password-btn', 'click', openChangePasswordModal);
    safeAddEventListener('logout-btn', 'click', logout);
    
    // Change password modal
    safeAddEventListener('close-change-password-modal', 'click', closeChangePasswordModal);
    safeAddEventListener('cancel-change-password', 'click', closeChangePasswordModal);
    safeAddEventListener('save-change-password', 'click', changePassword);

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

    // Sidebar toggle
    safeAddEventListener('sidebar-toggle', 'click', toggleSidebar);

    // Kill app functionality
    safeAddEventListener('kill-app-btn', 'click', killApp);

    // Import tasks functionality
    safeAddEventListener('import-tasks-btn', 'click', openImportModal);
    safeAddEventListener('close-import-modal', 'click', closeImportModal);
    safeAddEventListener('cancel-import', 'click', closeImportModal);
    safeAddEventListener('confirm-import', 'click', confirmImport);
    safeAddEventListener('import-file', 'change', previewImportFile);
    safeAddEventListener('download-sample', 'click', downloadSampleCSV);

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
    // Authentication check disabled - no authentication needed
    console.log('navigateToPage called with page:', page);
    
    if (!page) {
        console.error('No page specified for navigation');
        return;
    }
    
    // Handle special navigation items
    if (page === 'toggle') {
        // Sidebar toggle - don't navigate, just toggle
        toggleSidebar();
        return;
    }
    
    if (page === 'kill') {
        // Kill app - don't navigate, just kill
        killApp();
        return;
    }
    
    // Update navigation
    console.log('Updating navigation for page:', page);
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeNavItem = document.querySelector(`[data-page="${page}"]`);
    if (activeNavItem) {
        activeNavItem.classList.add('active');
        console.log('Set active nav item:', activeNavItem);
    } else {
        console.error('Could not find nav item with data-page:', page);
    }

    // Update pages
    console.log('Updating pages for page:', page);
    document.querySelectorAll('.page').forEach(pageEl => {
        pageEl.classList.remove('active');
    });
    const targetPage = document.getElementById(`${page}-page`);
    if (targetPage) {
        targetPage.classList.add('active');
        console.log('Set active page:', targetPage);
    } else {
        console.error('Could not find page element with id:', `${page}-page`);
    }

    AppState.set('currentPage', page);

    // Load page-specific data
    if (page === 'tasks') {
        loadTasks();
    } else if (page === 'planner') {
        // Load tasks first, then planner data will be loaded automatically
        loadTasks();
    } else if (page === 'analytics') {
        updateDashboardStats();
    }
}

// Task Management
async function loadTasks() {
    const MAX_RETRIES = 3;
    const TIMEOUT = 10000; // 10 seconds
    
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
        try {
            showLoading(true);
            
            // Add timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), TIMEOUT);
            
            const response = await fetch('/api/tasks', {
                signal: controller.signal
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                if (response.status === 401) {
                    Logger.log('Authentication required, showing login modal');
                    showAuthModal('login');
                    tasks = [];
                    showLoading(false); // Hide loading overlay on auth error
                    return;
                }
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            AppState.setTasks(Array.isArray(data) ? data : []);
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks(AppState.get('currentFilter'));
            } else if (AppState.get('currentPage') === 'analytics') {
                renderRecentTasks();
            } else if (AppState.get('currentPage') === 'planner') {
                loadPlannerData(); // Load both available and scheduled tasks
            }
            
            updateDashboardStats();
            Logger.log(`Loaded ${AppState.getTasks().length} tasks`);
            showLoading(false); // Hide loading overlay on success
            return; // Success
            
        } catch (error) {
            Logger.error(`Load tasks attempt ${attempt} failed:`, error);
            
            if (attempt === MAX_RETRIES) {
                // Final attempt failed
                if (error.name === 'AbortError') {
                    showNotification('Request timeout. Please check your connection and try again.', 'error');
                } else if (!navigator.onLine) {
                    showNotification('You are offline. Please check your internet connection.', 'error');
                } else {
                    showNotification(`Failed to load tasks: ${error.message}`, 'error');
                }
                tasks = [];
            } else {
                // Wait before retry (exponential backoff)
                await new Promise(resolve => setTimeout(resolve, 1000 * attempt));
            }
        } finally {
            if (attempt === MAX_RETRIES) {
                showLoading(false);
            }
        }
    }
}

async function createTask(taskData) {
    try {
        const response = await makeAuthenticatedRequest('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            const newTask = await response.json();
            AppState.addTask(newTask);
            updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
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
        const response = await makeAuthenticatedRequest(`/api/tasks/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify(taskData)
        });

        if (response.ok) {
            const updatedTask = await response.json();
            AppState.updateTask(taskId, updatedTask);
            
            updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
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
        const response = await makeAuthenticatedRequest(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            AppState.removeTask(taskId);
            updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
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
            AppState.updateTask(taskId, completedTask);
            
            updateDashboardStats();
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
            } else if (AppState.get('currentPage') === 'dashboard') {
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
function renderTasks(filter = AppState.get('currentFilter')) {
    const tasksList = document.getElementById('tasks-list');
    
    console.log('renderTasks called with:', {
        filter,
        currentLayout: AppState.get('currentLayout'),
        tasksLength: AppState.getTasks() ? AppState.getTasks().length : 'tasks is null/undefined',
        isAuthenticated: AppState.get('isAuthenticated'),
        passwordSet: AppState.get('passwordSet')
    });
    
    // Ensure tasks is an array before filtering
    const tasks = AppState.getTasks();
    if (!Array.isArray(tasks)) {
        console.warn('renderTasks: tasks is not an array:', tasks);
        AppState.setTasks([]);
        return;
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
        Logger.log('Rendering grid layout with', sortedTasks.length, 'tasks');
        const gridHTML = `
            <div class="tasks-grid">
                ${sortedTasks.map(task => {
                    const maxStrikes = 8;
                    const currentStrikes = task.strike_count || 0;
                    const progressPercentage = task.completed ? 100 : Math.min((currentStrikes / maxStrikes) * 100, 100);
                    const progressStep = task.completed ? maxStrikes : Math.min(currentStrikes + 1, maxStrikes);
                    
                    console.log(`Rendering task ${task.title}: struck_today=${task.struck_today}, completed=${task.completed}, strike_count=${task.strike_count}`);
                    
                    return `
                        <div class="task-card ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${task.strike_count > 1 ? 'restrike' : ''}" data-task-id="${task.id}">
                            <div class="task-actions-top-left">
                                ${task.struck_today && !task.completed ? `
                                    <button class="task-action undo-action" onclick="undoStrike('${task.id}')" title="Undo Strike">
                                        <i class="fas fa-undo"></i>
                                    </button>
                                ` : ''}
                                ${!task.completed && canStrikeTask(task) ? `
                                    <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                                        <i class="fas fa-check"></i>
                                    </button>
                                ` : !task.completed ? `
                                    <button class="task-action strike-btn disabled" title="Maximum strikes reached for today" disabled>
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
                            
                            <div class="task-project-top-right">
                                ${task.project ? `<span class="task-project-badge">${sanitizeHTML(task.project)}</span>` : ''}
                            </div>
                            
                            <div class="task-content-main">
                                <h3 class="task-title-main ${task.struck_today ? 'struck-today' : ''}">${sanitizeHTML(task.title)}</h3>
                                ${task.description ? `<p class="task-description-main">${sanitizeHTML(task.description)}</p>` : ''}
                            </div>
                            
                            <div class="task-duration-bottom-right">
                                <span class="task-duration-badge">${task.duration || 60} min</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
        Logger.log('Generated grid HTML');
        tasksList.innerHTML = gridHTML;
    } else {
        tasksList.innerHTML = sortedTasks.map(task => `
        <div class="task-item ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${task.strike_count > 1 ? 'restrike' : ''}" data-task-id="${task.id}">
            <div class="task-project-tag">
                ${task.project ? `<span class="project-tag">${sanitizeHTML(task.project)}</span>` : '<span class="project-tag no-project">No Project</span>'}
            </div>
            <div class="task-content">
                <h3 class="task-title ${task.struck_today ? 'struck-today' : ''}">${sanitizeHTML(task.title)}</h3>
                ${task.description ? `<p class="task-description">${sanitizeHTML(task.description)}</p>` : ''}
                ${task.strike_report ? `<p class="strike-report"><em>Last strike: ${sanitizeHTML(task.strike_report)}</em></p>` : ''}
            </div>
            <div class="task-actions">
                ${task.struck_today && !task.completed ? `
                    <button class="task-action undo-action" onclick="undoStrike('${task.id}')" title="Undo Strike">
                        <i class="fas fa-undo"></i>
                    </button>
                ` : ''}
                ${!task.completed && canStrikeTask(task) ? `
                    <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                        <i class="fas fa-check"></i>
                    </button>
                ` : !task.completed ? `
                    <button class="task-action strike-btn disabled" title="Maximum strikes reached for today" disabled>
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
    `).join('');
    }
}

function renderRecentTasks() {
    const recentTasksList = document.getElementById('recent-tasks-list');
    const tasks = AppState.getTasks();
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
    const tasks = AppState.getTasks();
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
    const tasks = AppState.getTasks();
    const completedTasks = tasks.filter(task => task.completed);
    if (completedTasks.length === 0) return 0;
    
    // For demo purposes, return a random streak
    return Math.min(completedTasks.length, 30);
}

function calculateProductivityScore() {
    const tasks = AppState.getTasks();
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
    // Create 30-minute intervals (48 slots total: 24 hours * 2)
    const timeSlots = [];
    for (let hour = 0; hour < 24; hour++) {
        timeSlots.push({ hour, minute: 0 });
        timeSlots.push({ hour, minute: 30 });
    }
    
    timeGrid.innerHTML = timeSlots.map(slot => `
        <div class="time-slot" data-hour="${slot.hour}" data-minute="${slot.minute}">
            <div class="time-label">${formatTime(slot.hour, slot.minute)}</div>
            <div class="time-content" data-hour="${slot.hour}" data-minute="${slot.minute}">
                <!-- Scheduled tasks will be added here -->
            </div>
        </div>
    `).join('');
    
    setupDragAndDrop();
}

function formatTime(hour, minute) {
    const period = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    return `${displayHour}:${minute.toString().padStart(2, '0')} ${period}`;
}

function formatHour(hour) {
    const period = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour === 0 ? 12 : hour > 12 ? hour - 12 : hour;
    return `${displayHour}:00 ${period}`;
}

// Store event handlers to prevent memory leaks
const dragHandlers = new WeakMap();

function setupDragAndDrop() {
    Logger.log('Setting up drag and drop...');
    
    // Clean up old listeners first
    const oldDraggables = document.querySelectorAll('.draggable-task, .scheduled-task');
    oldDraggables.forEach(element => {
        const handlers = dragHandlers.get(element);
        if (handlers) {
            element.removeEventListener('dragstart', handlers.dragstart);
            element.removeEventListener('dragend', handlers.dragend);
        }
    });
    
    // Make tasks draggable
    const draggableTasks = document.querySelectorAll('.draggable-task');
    Logger.log('Found draggable tasks:', draggableTasks.length);
    
    draggableTasks.forEach(task => {
        task.draggable = true;
        const handlers = {
            dragstart: handleDragStart,
            dragend: handleDragEnd
        };
        task.addEventListener('dragstart', handlers.dragstart);
        task.addEventListener('dragend', handlers.dragend);
        dragHandlers.set(task, handlers);
    });

    // Clean up old time slot listeners
    const oldSlots = document.querySelectorAll('.time-content');
    oldSlots.forEach(slot => {
        const handlers = dragHandlers.get(slot);
        if (handlers) {
            slot.removeEventListener('dragover', handlers.dragover);
            slot.removeEventListener('drop', handlers.drop);
            slot.removeEventListener('dragenter', handlers.dragenter);
            slot.removeEventListener('dragleave', handlers.dragleave);
        }
    });
    
    // Make time slots droppable
    const timeContents = document.querySelectorAll('.time-content');
    Logger.log('Found time slots:', timeContents.length);
    
    timeContents.forEach(slot => {
        const handlers = {
            dragover: handleDragOver,
            drop: handleDrop,
            dragenter: handleDragEnter,
            dragleave: handleDragLeave
        };
        slot.addEventListener('dragover', handlers.dragover);
        slot.addEventListener('drop', handlers.drop);
        slot.addEventListener('dragenter', handlers.dragenter);
        slot.addEventListener('dragleave', handlers.dragleave);
        dragHandlers.set(slot, handlers);
    });
    
    // Make scheduled tasks draggable
    const scheduledTasks = document.querySelectorAll('.scheduled-task');
    Logger.log('Found scheduled tasks:', scheduledTasks.length);
    
    scheduledTasks.forEach(task => {
        task.draggable = true;
        const handlers = {
            dragstart: handleDragStart,
            dragend: handleDragEnd
        };
        task.addEventListener('dragstart', handlers.dragstart);
        task.addEventListener('dragend', handlers.dragend);
        dragHandlers.set(task, handlers);
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
    const minute = e.target.dataset.minute;
    
    console.log('Dropping task:', taskId, 'at time:', `${hour}:${minute}`);
    
    // Check if this is a scheduled task being moved
    const scheduledTask = document.querySelector(`.scheduled-task[data-task-id="${taskId}"]`);
    if (scheduledTask) {
        // Remove from current time slot
        scheduledTask.remove();
    }
    
    // Schedule task with its actual duration
    const tasks = AppState.getTasks();
    const task = tasks.find(t => t.id === taskId);
    const taskDuration = task ? (task.duration || 60) : 60;
    
    try {
        const response = await fetch(`/api/tasks/${taskId}/schedule`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                hour: `${hour}:${minute}`,
                duration: taskDuration,
                date: new Date().toISOString().split('T')[0] // Send current date
            })
        });
        
        if (response.ok) {
            // Immediately remove the dragged task from available tasks for visual feedback
            const draggedTask = document.querySelector(`.draggable-task[data-task-id="${taskId}"]`);
            if (draggedTask) {
                draggedTask.remove();
            }
            
            // Refresh tasks data from server
            await loadTasks();
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
    const tasks = AppState.getTasks();
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
    console.log('loadPlannerData called');
    console.log('Current page:', AppState.get('currentPage'));
    console.log('Tasks available:', AppState.getTasks());
    
    generateTimeSlots(); // Initialize the time grid first
    loadAvailableTasks();
    loadScheduledTasks();
}

function loadAvailableTasks() {
    const availableTasks = document.getElementById('available-tasks');
    
    console.log('Loading available tasks...');
    const tasks = AppState.getTasks();
    console.log('Total tasks:', tasks.length);
    console.log('Tasks:', tasks);
    
    if (!Array.isArray(tasks)) {
        console.error('Tasks is not an array:', tasks);
        availableTasks.innerHTML = '<p>Error loading tasks.</p>';
        return;
    }
    
    const unscheduledTasks = tasks.filter(task => {
        const isUnscheduled = !task.scheduled_hour;
        const isNotCompleted = !task.completed;
        console.log(`Task ${task.title}: scheduled_hour=${task.scheduled_hour}, completed=${task.completed}, unscheduled=${isUnscheduled}, notCompleted=${isNotCompleted}`);
        return isUnscheduled && isNotCompleted;
    });
    
    console.log('Unscheduled tasks:', unscheduledTasks);
    console.log('Available tasks container:', availableTasks);
    
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
    const currentDate = new Date(); // Always use current date, not stored date
    const scheduledDate = currentDate.toISOString().split('T')[0];
    const tasks = AppState.getTasks();
    
    // Filter tasks scheduled for today OR tasks without a scheduled_date (legacy tasks)
    const scheduledTasks = tasks.filter(task => 
        task.scheduled_hour && 
        (task.scheduled_date === scheduledDate || !task.scheduled_date) &&
        !task.completed
    );
    
    console.log('loadScheduledTasks - currentDate:', currentDate);
    console.log('loadScheduledTasks - scheduledDate:', scheduledDate);
    console.log('loadScheduledTasks - all tasks:', tasks);
    console.log('loadScheduledTasks - scheduled tasks:', scheduledTasks);
    
    // Clear existing scheduled tasks and continuations
    document.querySelectorAll('.scheduled-task').forEach(task => task.remove());
    document.querySelectorAll('.scheduled-task-continuation').forEach(task => task.remove());
    
    // Add scheduled tasks to their time slots
    scheduledTasks.forEach(task => {
        // Parse the scheduled hour (format: "HH:MM")
        const timeParts = task.scheduled_hour.split(':');
        if (timeParts.length !== 2) {
            console.error(`Invalid scheduled_hour format: ${task.scheduled_hour}`);
            return;
        }
        
        const startHour = parseInt(timeParts[0]);
        const startMinute = parseInt(timeParts[1]);
        const taskDuration = parseInt(task.duration) || 60;
        
        // Validate parsed values
        if (isNaN(startHour) || isNaN(startMinute)) {
            console.error(`Invalid time values: hour=${startHour}, minute=${startMinute}`);
            return;
        }
        
        console.log(`Loading task: ${task.title}, Duration: ${taskDuration}min, Start: ${startHour}:${startMinute}`);
        console.log(`Looking for time slot with data-hour="${startHour}" data-minute="${startMinute}"`);
        
        // Calculate how many 30-minute slots this task spans
        const slotsNeeded = Math.ceil(taskDuration / 30);
        console.log(`Task spans ${slotsNeeded} slots`);
        
        // Create the task element
        const scheduledTaskEl = document.createElement('div');
        scheduledTaskEl.className = 'scheduled-task';
        if (slotsNeeded > 1) {
            scheduledTaskEl.classList.add('has-continuation');
        }
        scheduledTaskEl.innerHTML = `
            <div class="scheduled-task-header">
                <h4>${task.title}</h4>
                <button class="remove-task-btn" onclick="unscheduleTask('${task.id}')" title="Remove from planner">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <p class="task-duration">${taskDuration} min</p>
            ${task.description ? `<p class="task-description">${task.description}</p>` : ''}
        `;
        scheduledTaskEl.dataset.taskId = task.id;
        
        // Add the task to the starting time slot
        const startTimeContent = document.querySelector(`.time-content[data-hour="${startHour}"][data-minute="${startMinute}"]`);
        console.log(`Found time slot:`, startTimeContent);
        if (startTimeContent) {
            startTimeContent.appendChild(scheduledTaskEl);
            console.log(`Successfully added task to time slot`);
            
            // If task spans multiple slots, add visual indicators to subsequent slots
            for (let i = 1; i < slotsNeeded; i++) {
                let nextHour = startHour;
                let nextMinute = startMinute + (i * 30);
                
                // Handle hour overflow
                if (nextMinute >= 60) {
                    nextHour += Math.floor(nextMinute / 60);
                    nextMinute = nextMinute % 60;
                }
                
                // Don't go beyond 24 hours
                if (nextHour < 24) {
                    const nextTimeContent = document.querySelector(`.time-content[data-hour="${nextHour}"][data-minute="${nextMinute}"]`);
                    if (nextTimeContent) {
                        const continuationEl = document.createElement('div');
                        continuationEl.className = 'scheduled-task-continuation';
                        continuationEl.innerHTML = `
                            <div class="task-continuation-line"></div>
                            <span class="task-continuation-text">↳ ${task.title}</span>
                        `;
                        continuationEl.dataset.taskId = task.id;
                        continuationEl.dataset.isContinuation = 'true';
                        nextTimeContent.appendChild(continuationEl);
                    }
                }
            }
        } else {
            console.error(`Time slot not found for hour: ${startHour}, minute: ${startMinute}`);
            console.log('Available time slots:', document.querySelectorAll('.time-content'));
        }
    });
    
    // Re-setup drag and drop for scheduled tasks
    setupDragAndDrop();
}

function changeDate(days) {
    const currentDate = AppState.get('currentDate');
    currentDate.setDate(currentDate.getDate() + days);
    AppState.set('currentDate', currentDate);
    updateCurrentDate();
    loadPlannerData();
}

function updateCurrentDate() {
    const dateElement = document.getElementById('current-date');
    const today = new Date();
    const currentDate = AppState.get('currentDate');
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

function updateDateDisplay() {
    // Alias for updateCurrentDate to maintain compatibility
    updateCurrentDate();
}

// Settings Functions
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const settings = await response.json();
        AppState.set('currentSettings', settings);
        
        document.getElementById('autostart-toggle').checked = settings.autostart || false;
        document.getElementById('autosave-interval').value = settings.autosave_interval || 30;
        document.getElementById('theme-selector').value = settings.theme || 'light';
        document.getElementById('finish-selector').value = settings.finish || 'glossy';
        document.getElementById('intensity-selector').value = settings.intensity || '5';
        document.getElementById('dpi-selector').value = settings.dpi_scale || 100;
        
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
    const settings = AppState.get('currentSettings') || {};
    const theme = settings.theme || 'light';
    const finish = settings.finish || 'glossy';
    const intensity = settings.intensity || '5';
    const dpiScale = settings.dpi_scale || 100;
    
    // Apply theme
    document.body.setAttribute('data-theme', theme);
    
    // Apply finish
    document.body.setAttribute('data-finish', finish);
    
    // Apply intensity
    document.body.setAttribute('data-intensity', intensity);
    
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
            const settings = AppState.get('currentSettings') || {};
            settings.theme = theme;
            AppState.set('currentSettings', settings);
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

async function updateFinish() {
    const finish = document.getElementById('finish-selector').value;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ finish: finish })
        });

        if (response.ok) {
            const settings = AppState.get('currentSettings') || {};
            settings.finish = finish;
            AppState.set('currentSettings', settings);
            applyThemeAndDPI();
            showNotification('Finish updated successfully!', 'success');
        } else {
            throw new Error('Failed to update finish');
        }
    } catch (error) {
        console.error('Error updating finish:', error);
        showNotification('Error updating finish', 'error');
    }
}

async function updateIntensity() {
    const intensity = document.getElementById('intensity-selector').value;
    
    try {
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ intensity: intensity })
        });

        if (response.ok) {
            const settings = AppState.get('currentSettings') || {};
            settings.intensity = intensity;
            AppState.set('currentSettings', settings);
            applyThemeAndDPI();
            showNotification('Color intensity updated successfully!', 'success');
        } else {
            throw new Error('Failed to update intensity');
        }
    } catch (error) {
        console.error('Error updating intensity:', error);
        showNotification('Error updating color intensity', 'error');
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
            const settings = AppState.get('currentSettings') || {};
            settings.dpi_scale = dpiScale;
            AppState.set('currentSettings', settings);
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
// Password modal functions removed - no authentication needed

// Add missing closePasswordModal function to prevent errors
function closePasswordModal() {
    // This function is called by event listeners but the modal doesn't exist
    // Just log for debugging purposes
    console.log('closePasswordModal called - no password modal to close');
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

// Task strike limitation functions
function canStrikeTask(task) {
    const today = new Date().toDateString();
    const taskStrikesToday = task.daily_strikes || {};
    
    // Check if task has been struck twice today
    return (taskStrikesToday[today] || 0) < 2;
}

function getTaskStrikesToday(task) {
    const today = new Date().toDateString();
    return (task.daily_strikes || {})[today] || 0;
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
    
    // Check if task can still be struck today
    const tasks = AppState.get('tasks');
    const task = tasks.find(t => t.id === currentStrikeTaskId);
    if (!canStrikeTask(task)) {
        showNotification('Maximum strikes reached for today', 'error');
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
            
            // Handle specific error for maximum strikes reached
            if (errorData.error && errorData.error.includes('Maximum strikes reached')) {
                showNotification('Maximum strikes reached for today', 'error');
                closeStrikeModal();
                // Refresh tasks to update UI
                await loadTasks();
            } else {
                throw new Error(errorData.error || 'Failed to strike task');
            }
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
    // Get available tasks (not scheduled) from AppState
    const allTasks = AppState.get('tasks') || [];
    const availableTasks = allTasks.filter(task => !task.completed && !task.scheduled_hour);
    
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
            // FIXED: Reload both available and scheduled tasks
            await loadTasks(); // Refresh global tasks array
            loadPlannerData(); // Reload entire planner
            showNotification('Task removed from planner! ↩️', 'success');
            Logger.log(`Task ${taskId} unscheduled`);
        } else {
            throw new Error('Failed to unschedule task');
        }
    } catch (error) {
        Logger.error('Error unscheduling task:', error);
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
    const settings = AppState.get('currentSettings') || {};
    const resetTime = settings.daily_reset_time || '09:00';
    scheduleDailyReset(resetTime);
}

function scheduleDailyReset(resetTime) {
    const dailyResetTimer = AppState.get('dailyResetTimer');
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
    
    const timer = setTimeout(() => {
        resetDailyStrikes();
        scheduleDailyReset(resetTime); // Schedule next reset
    }, timeUntilReset);
    
    AppState.set('dailyResetTimer', timer);
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
    AppState.set('currentLayout', layout);
    
    // Update active button
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-layout="${layout}"]`).classList.add('active');
    
    // Re-render tasks with new layout
    if (AppState.get('currentPage') === 'tasks') {
        renderTasks();
    }
}

// Sidebar Functions
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const sidebarToggle = document.querySelector('#sidebar-toggle');

    sidebar.classList.toggle('open');
    
    // Toggle active state for visual feedback
    if (sidebarToggle) {
        sidebarToggle.classList.toggle('active');
    }

    // On mobile, toggle sidebar visibility
    if (window.innerWidth <= 768) {
        if (sidebar.style.transform === 'translateX(0px)' || !sidebar.style.transform) {
            sidebar.style.transform = 'translateX(-100%)';
        } else {
            sidebar.style.transform = 'translateX(0px)';
        }
    }
}

// Kill App Function
function killApp() {
    // Show confirmation dialog
    const confirmed = confirm(
        'Are you sure you want to stop the Shakshuka server?\n\n' +
        'This will:\n' +
        '• Close the web application\n' +
        '• Stop the server process\n' +
        '• You will need to restart manually\n\n' +
        'Click OK to continue or Cancel to abort.'
    );
    
    if (!confirmed) {
        return;
    }
    
    // Show loading state
    const killBtn = document.querySelector('#kill-app-btn');
    if (killBtn) {
        const originalHTML = killBtn.innerHTML;
        killBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i><span>Stopping...</span>';
        killBtn.style.pointerEvents = 'none';
        
        // Try to call the backend kill endpoint
        fetch('/api/kill-app', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
        .then(response => {
            if (response.ok) {
                // Show success message briefly
                killBtn.innerHTML = '<i class="fas fa-check"></i><span>Stopped!</span>';
                killBtn.style.color = '#28a745';
                
                // Close the browser tab/window after a short delay
                setTimeout(() => {
                    window.close();
                }, 1500);
            } else {
                throw new Error('Failed to stop server');
            }
        })
        .catch(error => {
            console.error('Error stopping server:', error);
            
            // Fallback: try to run Stop-Shakshuka.bat via a different method
            killBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i><span>Fallback...</span>';
            
            // Try to trigger the stop script
            try {
                // Create a hidden iframe to trigger the stop script
                const iframe = document.createElement('iframe');
                iframe.style.display = 'none';
                iframe.src = 'data:text/html,<script>window.parent.postMessage("stop-server", "*");</script>';
                document.body.appendChild(iframe);
                
                // Listen for the message
                window.addEventListener('message', function(event) {
                    if (event.data === 'stop-server') {
                        // Show final message and close
                        killBtn.innerHTML = '<i class="fas fa-power-off"></i><span>Server Stopped</span>';
                        setTimeout(() => {
                            window.close();
                        }, 1000);
                    }
                });
                
                // Clean up iframe after a delay
                setTimeout(() => {
                    if (iframe.parentNode) {
                        iframe.parentNode.removeChild(iframe);
                    }
                }, 2000);
                
            } catch (fallbackError) {
                console.error('Fallback method failed:', fallbackError);
                
                // Final fallback: just show message and let user close manually
                killBtn.innerHTML = '<i class="fas fa-info-circle"></i><span>Close Browser</span>';
                killBtn.style.color = '#ffc107';
                
                alert(
                    'Unable to automatically stop the server.\n\n' +
                    'Please:\n' +
                    '1. Close this browser tab/window\n' +
                    '2. Run "Stop-Shakshuka.bat" manually\n' +
                    '3. Or use Ctrl+C in the command window'
                );
            }
            
            // Restore button after error
            setTimeout(() => {
                killBtn.innerHTML = originalHTML;
                killBtn.style.pointerEvents = 'auto';
                killBtn.style.color = '';
            }, 3000);
        });
    }
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
        // Ask user for backup location
        const backupLocation = await showBackupLocationDialog();
        if (!backupLocation) {
            return; // User cancelled
        }
        
        showNotification('Creating backup...', 'info');
        
        const response = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                type: 'manual',
                location: backupLocation
            })
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

function showBackupLocationDialog() {
    return new Promise((resolve) => {
        // Create a simple dialog for backup location
        const dialog = document.createElement('div');
        dialog.className = 'modal active';
        dialog.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Choose Backup Location</h3>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label for="backup-location">Backup Location:</label>
                        <input type="text" id="backup-location" placeholder="Enter folder path or leave empty for default" style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <button class="btn-primary" onclick="confirmBackupLocation()">Create Backup</button>
                        <button class="btn-secondary" onclick="cancelBackupLocation()">Cancel</button>
                    </div>
                </div>
            </div>
        `;
        
        document.body.appendChild(dialog);
        
        // Global functions for the dialog
        window.confirmBackupLocation = () => {
            const location = document.getElementById('backup-location').value.trim();
            dialog.remove();
            resolve(location || null);
        };
        
        window.cancelBackupLocation = () => {
            dialog.remove();
            resolve(null);
        };
        
        // Focus the input
        setTimeout(() => {
            document.getElementById('backup-location').focus();
        }, 100);
    });
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
            const settings = AppState.get('currentSettings') || {};
            settings.daily_reset_time = resetTime;
            AppState.set('currentSettings', settings);
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

// Consolidated save function to avoid duplication
async function saveTaskCommon(taskData, modalCloseFn) {
    // Validation
    if (!taskData.title || !taskData.title.trim()) {
        showNotification('Please enter a task title', 'error');
        return false;
    }
    
    if (taskData.title.length > 200) {
        showNotification('Task title is too long (max 200 characters)', 'error');
        return false;
    }
    
    if (taskData.estimated_duration) {
        const duration = parseInt(taskData.estimated_duration);
        if (isNaN(duration) || duration < 5 || duration > 480) {
            showNotification('Duration must be between 5 and 480 minutes', 'error');
            return false;
        }
    }
    
    if (taskData.due_date) {
        const dueDate = new Date(taskData.due_date);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        if (dueDate < today) {
            if (!confirm('Due date is in the past. Continue anyway?')) {
                return false;
            }
        }
    }

    try {
        if (editingTaskId) {
            await updateTask(editingTaskId, taskData);
        } else {
            await createTask(taskData);
        }
        
        modalCloseFn();
        return true;
    } catch (error) {
        Logger.error('Error saving task:', error);
        return false;
    }
}

// Duplicate saveTask function removed - using the first one

async function saveQuickTask() {
    const taskData = {
        title: document.getElementById('quick-task-title').value.trim(),
        description: '',
        project: '',
        estimated_duration: 60
    };
    
    await saveTaskCommon(taskData, closeQuickAddModal);
}
// Import Tasks Functions
function openImportModal() {
    const modal = document.getElementById('import-modal');
    modal.classList.add('active');
    
    // Reset form
    document.getElementById('import-form').reset();
    document.getElementById('import-preview').style.display = 'none';
    document.getElementById('preview-content').innerHTML = '';
}

function closeImportModal() {
    const modal = document.getElementById('import-modal');
    modal.classList.remove('active');
}

function previewImportFile() {
    const fileInput = document.getElementById('import-file');
    const file = fileInput.files[0];
    
    if (!file) {
        document.getElementById('import-preview').style.display = 'none';
        return;
    }
    
    const reader = new FileReader();
    reader.onload = function(e) {
        const content = e.target.result;
        const preview = document.getElementById('preview-content');
        
        try {
            let previewHtml = '';
            const fileExtension = file.name.toLowerCase().split('.').pop();
            
            if (fileExtension === 'csv') {
                previewHtml = parseCSVPreview(content);
            } else if (fileExtension === 'txt') {
                previewHtml = parseTXTPreview(content);
            } else {
                previewHtml = '<p style="color: red;">Unsupported file format</p>';
            }
            
            preview.innerHTML = previewHtml;
            document.getElementById('import-preview').style.display = 'block';
        } catch (error) {
            preview.innerHTML = `<p style="color: red;">Error parsing file: ${error.message}</p>`;
            document.getElementById('import-preview').style.display = 'block';
        }
    };
    
    reader.readAsText(file);
}

function parseCSVPreview(content) {
    const lines = content.split('\n');
    const header = lines[0].split(',').map(h => h.trim());
    
    let html = '<div class="preview-table">';
    html += '<table style="width: 100%; border-collapse: collapse;">';
    html += '<thead><tr>';
    header.forEach(h => {
        html += `<th style="border: 1px solid #ddd; padding: 8px; background: #f5f5f5;">${h}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    // Show first 5 rows
    for (let i = 1; i < Math.min(6, lines.length); i++) {
        if (lines[i].trim()) {
            const row = lines[i].split(',').map(c => c.trim());
            html += '<tr>';
            row.forEach(cell => {
                html += `<td style="border: 1px solid #ddd; padding: 8px;">${cell}</td>`;
            });
            html += '</tr>';
        }
    }
    
    html += '</tbody></table>';
    html += `<p><em>Showing first ${Math.min(5, lines.length - 1)} rows of ${lines.length - 1} total rows</em></p>`;
    html += '</div>';
    
    return html;
}

function parseTXTPreview(content) {
    const lines = content.split('\n').filter(line => line.trim() && !line.trim().startsWith('#'));
    
    let html = '<div class="preview-list">';
    html += '<ul>';
    
    // Show first 5 lines
    for (let i = 0; i < Math.min(5, lines.length); i++) {
        const parts = lines[i].split('|').map(p => p.trim());
        html += `<li><strong>${parts[0]}</strong>`;
        if (parts[1]) html += ` - ${parts[1]}`;
        if (parts[2]) html += ` (${parts[2]})`;
        html += '</li>';
    }
    
    html += '</ul>';
    html += `<p><em>Showing first ${Math.min(5, lines.length)} tasks of ${lines.length} total tasks</em></p>`;
    html += '</div>';
    
    return html;
}

async function confirmImport() {
    const fileInput = document.getElementById('import-file');
    const file = fileInput.files[0];
    const overwrite = document.getElementById('import-overwrite').checked;
    
    if (!file) {
        showNotification('Please select a file to import', 'error');
        return;
    }
    
    try {
        showLoading(true);
        
        const formData = new FormData();
        formData.append('file', file);
        formData.append('overwrite', overwrite);
        
        const response = await fetch('/api/tasks/import', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showNotification(result.message, 'success');
            
            // Reload tasks
            await loadTasks();
            
            // Show errors if any
            if (result.errors && result.errors.length > 0) {
                console.warn('Import warnings:', result.errors);
                showNotification(`${result.errors.length} warnings during import`, 'warning');
            }
            
            closeImportModal();
        } else {
            showNotification(result.error || 'Import failed', 'error');
        }
    } catch (error) {
        console.error('Import error:', error);
        showNotification('Import failed: ' + error.message, 'error');
    } finally {
        showLoading(false);
    }
}

function downloadSampleCSV() {
    const sampleData = [
        ['title', 'description', 'project', 'duration', 'due_date', 'priority'],
        ['Complete project proposal', 'Write and submit the quarterly project proposal', 'Work', '120', '2024-01-15', 'high'],
        ['Buy groceries', 'Get milk, bread, eggs, and vegetables', 'Personal', '30', '2024-01-10', 'medium'],
        ['Review code changes', 'Review pull request #123 for the new feature', 'Work', '60', '2024-01-12', 'high'],
        ['Call dentist', 'Schedule annual dental checkup', 'Health', '15', '2024-01-20', 'low'],
        ['Update documentation', 'Update API documentation for new endpoints', 'Work', '90', '2024-01-18', 'medium']
    ];
    
    const csvContent = sampleData.map(row => row.join(',')).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'sample_tasks.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
    
    showNotification('Sample CSV template downloaded!', 'success');
}

// Duplicate functions removed - using the ones defined earlier in the file around line 414-420

async function autoSave() {
    // Auto-save functionality - just trigger a save of current tasks
    if (AppState.get('isAuthenticated')) {
        try {
            const tasks = AppState.get('tasks') || [];
            // Don't send empty tasks array - only save if there are actual tasks
            if (tasks.length > 0) {
                // The backend auto-save worker handles saving tasks automatically
                // This frontend auto-save is mainly for UI state
                console.log('Auto-save: Tasks are being saved by backend worker');
            }
        } catch (error) {
            console.error('Auto-save failed:', error);
        }
    }
}

// Account Management Functions
function openChangePasswordModal() {
    const modal = document.getElementById('change-password-modal');
    if (modal) {
        modal.style.display = 'flex';
        // Clear form
        document.getElementById('change-password-form').reset();
    }
}

function closeChangePasswordModal() {
    const modal = document.getElementById('change-password-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function changePassword() {
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    
    if (!currentPassword || !newPassword || !confirmPassword) {
        showNotification('Please fill in all password fields', 'error');
        return;
    }
    
    if (newPassword !== confirmPassword) {
        showNotification('New passwords do not match', 'error');
        return;
    }
    
    if (newPassword.length < 8) {
        showNotification('New password must be at least 8 characters long', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/auth/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                currentPassword,
                newPassword
            })
        });
        
        if (response.ok) {
            showNotification('Password changed successfully!', 'success');
            closeChangePasswordModal();
        } else {
            const error = await response.json();
            showNotification(error.message || 'Failed to change password', 'error');
        }
    } catch (error) {
        console.error('Error changing password:', error);
        showNotification('Failed to change password', 'error');
    }
}

async function logout() {
    if (confirm('Are you sure you want to logout? All unsaved changes will be lost.')) {
        try {
            const response = await fetch('/api/auth/logout', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                // Clear local state
                AppState.set('isAuthenticated', false);
                AppState.set('passwordSet', false);
                AppState.set('tasks', []);
                AppState.set('currentSettings', {});
                
                // Clear localStorage
                localStorage.removeItem('shakshuka_password');
                
                showNotification('Logged out successfully!', 'success');
                
                // Redirect to login or reload page
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                throw new Error('Logout failed');
            }
        } catch (error) {
            console.error('Error logging out:', error);
            showNotification('Failed to logout', 'error');
        }
    }
}
