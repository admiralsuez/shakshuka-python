/**
 * Main Application Entry Point
 * Imports and initializes all modules
 */

// Import core modules
import { AppState } from './core/app-state.js';
import { TaskAPI, SettingsAPI, APIError } from './core/api-client.js';
import { Logger, safeAddEventListener, safeShowNotification, escapeHtml, debounce } from './core/utils.js';

// Import page modules
import { TaskManager } from './pages/tasks.js';

// Global variables
let editingTaskId = null;

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded');
    initializeApp();
    setupEventListeners();
    checkAuthStatus();
});

// Initialize logging
function initializeLogging() {
    addLog('success', 'Shakshuka application started');
}

// Add log entry
function addLog(level, message) {
    const timestamp = new Date().toLocaleTimeString();
    const logEntry = {
        timestamp,
        level,
        message
    };
    
    AppState.set('developerLogs', [...AppState.get('developerLogs'), logEntry]);
    
    // Keep only last 100 logs
    const logs = AppState.get('developerLogs');
    if (logs.length > 100) {
        AppState.set('developerLogs', logs.slice(-100));
    }
}

// Initialize app
function initializeApp() {
    initializeLogging();
    Logger.log('Application initialized');
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

// Load all app data
function loadAppData() {
    TaskManager.loadTasks().catch(error => {
        Logger.error('Failed to load tasks:', error);
    });
    
    loadSettings().catch(error => {
        Logger.error('Failed to load settings:', error);
    });
}

// Load settings
async function loadSettings() {
    try {
        const settings = await SettingsAPI.get();
        AppState.set('currentSettings', settings);
    } catch (error) {
        Logger.error('Failed to load settings:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
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
            TaskManager.renderTasks(filter);
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
    console.log('Navigating to page:', page);
    
    // Update navigation
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    const activeNavItem = document.querySelector(`[data-page="${page}"]`);
    if (activeNavItem) {
        activeNavItem.classList.add('active');
    }

    // Update pages
    document.querySelectorAll('.page').forEach(pageEl => {
        pageEl.classList.remove('active');
    });
    const targetPage = document.getElementById(`${page}-page`);
    if (targetPage) {
        targetPage.classList.add('active');
    }

    AppState.set('currentPage', page);

    // Load page-specific data
    if (page === 'tasks') {
        TaskManager.loadTasks();
    } else if (page === 'planner') {
        loadPlannerData();
    } else if (page === 'analytics') {
        TaskManager.renderRecentTasks();
    }
}

// Task modal functions
function openTaskModal(taskId = null) {
    editingTaskId = taskId;
    const modal = document.getElementById('task-modal');
    const title = document.getElementById('modal-title');
    
    if (taskId) {
        const task = AppState.getTasks().find(t => t.id === taskId);
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

function clearTaskForm() {
    document.getElementById('task-form').reset();
}

function populateTaskForm(task) {
    document.getElementById('task-title').value = task.title || '';
    document.getElementById('task-description').value = task.description || '';
    document.getElementById('task-priority').value = task.priority || 'medium';
    document.getElementById('task-category').value = task.category || '';
    document.getElementById('task-due-date').value = task.due_date || '';
    document.getElementById('task-duration').value = task.estimated_duration || 60;
}

// Form submissions
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
        safeShowNotification('Please enter a task title', 'error');
        return;
    }

    try {
        if (editingTaskId) {
            await TaskManager.updateTask(editingTaskId, taskData);
        } else {
            await TaskManager.createTask(taskData);
        }
        
        closeTaskModal();
    } catch (error) {
        Logger.error('Error saving task:', error);
    }
}

async function saveQuickTask() {
    const title = document.getElementById('quick-task-title').value.trim();
    
    if (!title) {
        safeShowNotification('Please enter a task title', 'error');
        return;
    }

    const taskData = {
        title: title,
        description: '',
        priority: 'medium',
        category: '',
        due_date: '',
        estimated_duration: 60
    };

    try {
        await TaskManager.createTask(taskData);
        closeQuickAddModal();
    } catch (error) {
        Logger.error('Error saving quick task:', error);
    }
}

// Filter functions
function setActiveFilter(filter) {
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.querySelector(`[data-filter="${filter}"]`).classList.add('active');
    AppState.set('currentFilter', filter);
}

// Layout functions
function setLayout(layout) {
    AppState.set('currentLayout', layout);
    
    // Update active button
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-layout="${layout}"]`).classList.add('active');
    
    // Re-render tasks with new layout
    if (AppState.get('currentPage') === 'tasks') {
        TaskManager.renderTasks();
    }
}

// Sidebar functions
function toggleSidebar() {
    const sidebar = document.querySelector('.sidebar');
    const mainContent = document.querySelector('.main-content');
    const sidebarToggle = document.querySelector('#sidebar-toggle');

    if (sidebar.classList.contains('collapsed')) {
        sidebar.classList.remove('collapsed');
        mainContent.classList.remove('sidebar-collapsed');
        sidebarToggle.innerHTML = '<i class="fas fa-bars"></i><span>Toggle Sidebar</span>';
    } else {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('sidebar-collapsed');
        sidebarToggle.innerHTML = '<i class="fas fa-bars"></i>';
    }
}

// Placeholder functions for other features
function loadPlannerData() {
    Logger.log('Loading planner data');
}

function changeDate(direction) {
    Logger.log('Changing date:', direction);
}

function updateAutostart() {
    Logger.log('Updating autostart');
}

function updateAutosaveInterval() {
    Logger.log('Updating autosave interval');
}

function updateDailyResetTime() {
    Logger.log('Updating daily reset time');
}

function updateTheme() {
    Logger.log('Updating theme');
}

function updateFinish() {
    Logger.log('Updating finish');
}

function updateIntensity() {
    Logger.log('Updating intensity');
}

function updateDPI() {
    Logger.log('Updating DPI');
}

function exportData() {
    Logger.log('Exporting data');
}

function clearAllData() {
    Logger.log('Clearing all data');
}

function openLogsModal() {
    Logger.log('Opening logs modal');
}

function closeLogsModal() {
    Logger.log('Closing logs modal');
}

function clearLogs() {
    Logger.log('Clearing logs');
}

function displayLogs() {
    Logger.log('Displaying logs');
}

function closeStrikeModal() {
    Logger.log('Closing strike modal');
}

function strikeTaskToday() {
    Logger.log('Striking task today');
}

function strikeTaskForever() {
    Logger.log('Striking task forever');
}

function openScheduleModal() {
    Logger.log('Opening schedule modal');
}

function closeScheduleModal() {
    Logger.log('Closing schedule modal');
}

function confirmSchedule() {
    Logger.log('Confirming schedule');
}

function killApp() {
    Logger.log('Killing app');
}

function openImportModal() {
    Logger.log('Opening import modal');
}

function closeImportModal() {
    Logger.log('Closing import modal');
}

function confirmImport() {
    Logger.log('Confirming import');
}

function previewImportFile() {
    Logger.log('Previewing import file');
}

function downloadSampleCSV() {
    Logger.log('Downloading sample CSV');
}

// Make functions globally available
window.TaskManager = TaskManager;
window.navigateToPage = navigateToPage;
window.openTaskModal = openTaskModal;
window.closeTaskModal = closeTaskModal;
window.openQuickAddModal = openQuickAddModal;
window.closeQuickAddModal = closeQuickAddModal;
window.saveTask = saveTask;
window.saveQuickTask = saveQuickTask;
window.setLayout = setLayout;
window.toggleSidebar = toggleSidebar;
