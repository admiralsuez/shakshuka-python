// Main Shakshuka Application - Module Architecture

// Import all modules
// Note: These will be loaded in the HTML template in the correct order

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


// Setup all event listeners
// Page navigation
// Layout management
function setLayout(layout) {
    AppState.set('currentLayout', layout);

    // Update UI
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-layout="${layout}"]`).classList.add('active');

    // Apply layout changes
    const mainContent = document.querySelector('.main-content');
    if (layout === 'grid') {
        mainContent.classList.add('grid-layout');
    } else {
        mainContent.classList.remove('grid-layout');
    }
}

// Date navigation
function changeDate(days) {
    const currentDate = AppState.get('currentDate');
    const newDate = new Date(currentDate);
    newDate.setDate(currentDate.getDate() + days);

    AppState.set('currentDate', newDate);

    // Update UI
    const dateElement = document.getElementById('current-date');
    if (dateElement) {
        dateElement.textContent = Utils.formatDate(newDate);
    }

    // Reload data for new date if planner v2 is active
    if (AppState.get('currentPage') === 'planner') {
        if (typeof window.ensurePlannerV2Init === 'function') {
            window.ensurePlannerV2Init();
        }
    }
}

// Settings functions
async function updateAutostart() {
    const enabled = document.getElementById('autostart-toggle').checked;
    try {
        const response = await apiCall('/api/settings/autostart', {
            method: 'POST',
            body: JSON.stringify({ enabled })
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
        Utils.Logger.error('Error updating autostart:', error);
        showNotification('Error updating autostart setting', 'error');
    }
}

async function updateAutosaveInterval() {
    const interval = parseInt(document.getElementById('autosave-interval').value);
    try {
        const response = await apiCall('/api/settings/autosave', {
            method: 'POST',
            body: JSON.stringify({ interval })
        });

        if (response.ok) {
            showNotification('Autosave interval updated successfully!', 'success');
        } else {
            throw new Error('Failed to update autosave interval');
        }
    } catch (error) {
        Utils.Logger.error('Error updating autosave interval:', error);
        showNotification('Error updating autosave interval', 'error');
    }
}

async function updateDailyResetTime() {
    const time = document.getElementById('daily-reset-time').value;
    try {
        // Persist via settings endpoint and reschedule
        const response = await apiCall('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({ daily_reset_time: time })
        });
        if (response.ok) {
            try { if (typeof window.Settings?.load === 'function') await window.Settings.load(); } catch(e) {}
            try { if (typeof window.setupDailyReset === 'function') window.setupDailyReset(); } catch(e) {}
            Utils.safeShowNotification('Daily reset time updated', 'success');
        } else {
            Utils.safeShowNotification('Failed to update daily reset time', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to update daily reset time:', error);
        Utils.safeShowNotification('Failed to update daily reset time', 'error');
    }
}

async function updateTheme() {
    const theme = document.getElementById('theme-selector').value;
    
    try {
        console.log('Updating theme to:', theme);
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ theme: theme })
        });

        console.log('Theme update response:', response.status, response.statusText);

        if (response.ok) {
            const settings = AppState.get('currentSettings') || {};
            settings.theme = theme;
            AppState.set('currentSettings', settings);
            applyThemeAndDPI();
            showNotification('Theme updated successfully!', 'success');
        } else {
            const errorText = await response.text();
            console.error('Theme update failed:', response.status, errorText);
            throw new Error(`Failed to update theme: ${response.status} ${errorText}`);
        }
    } catch (error) {
        console.error('Error updating theme:', error);
        showNotification('Error updating theme', 'error');
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
        showNotification('Error updating intensity', 'error');
    }
}

// DPI update function is defined later in the file

// Data management
async function exportData() {
    try {
        Utils.showLoading(document.getElementById('export-data-btn'), 'Exporting...');

        const response = await Utils.makeAuthenticatedRequest('/api/export');
        const data = await response.json();

        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `shakshuka-backup-${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);

        Utils.hideLoading(document.getElementById('export-data-btn'), 'Export Data');
        Utils.safeShowNotification('Data exported successfully!', 'success');
    } catch (error) {
        Utils.Logger.error('Failed to export data:', error);
        Utils.hideLoading(document.getElementById('export-data-btn'), 'Export Data');
        Utils.safeShowNotification('Failed to export data', 'error');
    }
}

async function clearAllData() {
    if (!confirm('Are you sure you want to clear all data? This action cannot be undone.')) {
        return;
    }

    try {
        Utils.showLoading(document.getElementById('clear-data-btn'), 'Clearing...');

        const response = await Utils.makeAuthenticatedRequest('/api/clear', {
            method: 'POST'
        });

        if (response.ok) {
            AppState.setTasks([]);
            Tasks.renderTasks();
            Utils.safeShowNotification('All data cleared successfully!', 'success');
        } else {
            Utils.safeShowNotification('Failed to clear data', 'error');
        }

        Utils.hideLoading(document.getElementById('clear-data-btn'), 'Clear Data');
    } catch (error) {
        Utils.Logger.error('Failed to clear data:', error);
        Utils.hideLoading(document.getElementById('clear-data-btn'), 'Clear Data');
        Utils.safeShowNotification('Failed to clear data', 'error');
    }
}

// Modal management functions
function openLogsModal() {
    displayLogs();
    document.getElementById('logs-modal').style.display = 'flex';
}

function closeLogsModal() {
    document.getElementById('logs-modal').style.display = 'none';
}

function displayLogs() {
    const logs = AppState.get('developerLogs');
    const logsContainer = document.getElementById('logs-content');

    if (!logsContainer) return;

    logsContainer.innerHTML = '';

    if (logs.length === 0) {
        logsContainer.innerHTML = '<p>No logs available</p>';
        return;
    }

    logs.forEach(log => {
        const logEntry = document.createElement('div');
        logEntry.className = `log-entry ${log.type}`;
        logEntry.innerHTML = `
            <span class="log-timestamp">${log.timestamp}</span>
            <span class="log-message">${Utils.sanitizeHTML(log.message)}</span>
        `;
        logsContainer.appendChild(logEntry);
    });

    logsContainer.scrollTop = logsContainer.scrollHeight;
}

// Strike modal functions
function strikeTaskToday() {
    const taskId = AppState.get('strikeTaskId');
    if (taskId) {
        Tasks.strikeTaskToday(taskId);
    }
}

function strikeTaskForever() {
    const taskId = AppState.get('strikeTaskId');
    if (taskId) {
        Tasks.strikeTaskForever(taskId);
    }
}

// Backup and update modal functions
function closeBackupModal() {
    document.getElementById('backup-modal').style.display = 'none';
}

function closeUpdateModal() {
    document.getElementById('update-modal').style.display = 'none';
}

async function createBackup() {
    try {
        Utils.showLoading(document.getElementById('create-backup-btn'), 'Creating...');

        const response = await Utils.makeAuthenticatedRequest('/api/backup', {
            method: 'POST'
        });

        if (response.ok) {
            Utils.safeShowNotification('Backup created successfully!', 'success');
        } else {
            Utils.safeShowNotification('Failed to create backup', 'error');
        }

        Utils.hideLoading(document.getElementById('create-backup-btn'), 'Create Backup');
    } catch (error) {
        Utils.Logger.error('Failed to create backup:', error);
        Utils.hideLoading(document.getElementById('create-backup-btn'), 'Create Backup');
        Utils.safeShowNotification('Failed to create backup', 'error');
    }
}

async function restoreBackup() {
    const backupName = document.getElementById('backup-select').value;
    if (!backupName) {
        Utils.safeShowNotification('Please select a backup to restore', 'error');
        return;
    }

    try {
        Utils.showLoading(document.getElementById('restore-backup-btn'), 'Restoring...');

        const response = await Utils.makeAuthenticatedRequest(`/api/backup/${backupName}/restore`, {
            method: 'POST'
        });

        if (response.ok) {
            closeBackupModal();
            loadAppData();
            Utils.safeShowNotification('Backup restored successfully!', 'success');
        } else {
            Utils.safeShowNotification('Failed to restore backup', 'error');
        }

        Utils.hideLoading(document.getElementById('restore-backup-btn'), 'Restore Backup');
    } catch (error) {
        Utils.Logger.error('Failed to restore backup:', error);
        Utils.hideLoading(document.getElementById('restore-backup-btn'), 'Restore Backup');
        Utils.safeShowNotification('Failed to restore backup', 'error');
    }
}

async function downloadUpdate() {
    try {
        Utils.showLoading(document.getElementById('download-update-btn'), 'Downloading...');

        const response = await Utils.makeAuthenticatedRequest('/api/update/download', {
            method: 'POST'
        });

        if (response.ok) {
            Utils.safeShowNotification('Update downloaded successfully!', 'success');
        } else {
            Utils.safeShowNotification('Failed to download update', 'error');
        }

        Utils.hideLoading(document.getElementById('download-update-btn'), 'Download Update');
    } catch (error) {
        Utils.Logger.error('Failed to download update:', error);
        Utils.hideLoading(document.getElementById('download-update-btn'), 'Download Update');
        Utils.safeShowNotification('Failed to download update', 'error');
    }
}

async function installUpdate() {
    try {
        Utils.showLoading(document.getElementById('install-update-btn'), 'Installing...');

        const response = await Utils.makeAuthenticatedRequest('/api/update/install', {
            method: 'POST'
        });

        if (response.ok) {
            Utils.safeShowNotification('Update installed successfully! Please restart the application.', 'success');
        } else {
            Utils.safeShowNotification('Failed to install update', 'error');
        }

        Utils.hideLoading(document.getElementById('install-update-btn'), 'Install Update');
    } catch (error) {
        Utils.Logger.error('Failed to install update:', error);
        Utils.hideLoading(document.getElementById('install-update-btn'), 'Install Update');
        Utils.safeShowNotification('Failed to install update', 'error');
    }
}

// Update settings functions
async function updateUpdateSettings() {
    const autoUpdate = document.getElementById('auto-update-check')?.checked || false;
    const autoInstall = document.getElementById('auto-update-install')?.checked || false;
    const backupBeforeUpdate = document.getElementById('backup-before-update')?.checked || true;
    const githubAutoUpdate = document.getElementById('github-auto-update')?.checked || false;
    const checkInterval = 24; // fixed to 24 hours as requested

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/updates', {
            method: 'POST',
            body: JSON.stringify({ 
                channel: 'stable',
                auto_update: autoUpdate,
                auto_install: autoInstall,
                backup_before_update: backupBeforeUpdate,
                github_auto_update: githubAutoUpdate,
                github_branch: 'main',
                check_interval: checkInterval
            })
        });

        if (response.ok) {
            Utils.safeShowNotification('Update settings updated', 'success');
            try { if (typeof window.incrementSettingsChangeCount === 'function') window.incrementSettingsChangeCount(); } catch(e) {}
        } else {
            Utils.safeShowNotification('Failed to update settings', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to update settings:', error);
        Utils.safeShowNotification('Failed to update settings', 'error');
    }
}

async function updateBackupSettings() {
    const enabled = document.getElementById('backup-toggle').checked;

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/backups', {
            method: 'POST',
            body: JSON.stringify({ enabled })
        });

        if (response.ok) {
            Utils.safeShowNotification('Backup settings updated', 'success');
        } else {
            Utils.safeShowNotification('Failed to update backup settings', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to update backup settings:', error);
        Utils.safeShowNotification('Failed to update backup settings', 'error');
    }
}

// Account management
async function deleteAccount() {
    if (!confirm('Are you sure you want to delete your account? This will remove all your data permanently.')) {
        return;
    }

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/account/delete', {
            method: 'POST'
        });

        if (response.ok) {
            Utils.safeShowNotification('Account deleted successfully!', 'success');
            // Redirect or reload as needed
        } else {
            Utils.safeShowNotification('Failed to delete account', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to delete account:', error);
        Utils.safeShowNotification('Failed to delete account', 'error');
    }
}

// Password modal functions
function closePasswordModal() {
    document.getElementById('password-modal').style.display = 'none';
}

async function savePassword() {
    const currentPassword = document.getElementById('current-password').value;
    const newPassword = document.getElementById('new-password').value;
    const confirmPassword = document.getElementById('confirm-password').value;

    if (!currentPassword || !newPassword || !confirmPassword) {
        Utils.safeShowNotification('Please fill in all password fields', 'error');
        return;
    }

    if (newPassword !== confirmPassword) {
        Utils.safeShowNotification('New passwords do not match', 'error');
        return;
    }

    if (newPassword.length < 6) {
        Utils.safeShowNotification('New password must be at least 6 characters', 'error');
        return;
    }

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/account/password', {
            method: 'POST',
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword
            })
        });

        if (response.ok) {
            closePasswordModal();
            Utils.safeShowNotification('Password changed successfully!', 'success');
        } else {
            const error = await response.json();
            Utils.safeShowNotification(error.error || 'Failed to change password', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to change password:', error);
        Utils.safeShowNotification('Failed to change password', 'error');
    }
}

// Legacy functions that need to be implemented or removed
// These are referenced in the HTML but may not be defined yet

// Load settings page data
function loadSettingsPage() {
    // Populate reset time controls from current settings
    const settings = AppState.get('currentSettings') || {};
    const hourSelect = document.getElementById('reset-hour-select');
    const minuteSelect = document.getElementById('reset-minute-select');
    const periodSelect = document.getElementById('reset-period-select');
    
    if (hourSelect && minuteSelect && periodSelect && settings.daily_reset_time) {
        const timeStr = settings.daily_reset_time;
        console.log('[DEBUG] loadSettingsPage: Loading reset time from AppState:', timeStr);
        const [hours24, minutes] = timeStr.split(':').map(Number);
        console.log('[DEBUG] loadSettingsPage: Parsed hours24:', hours24, 'minutes:', minutes);
        
        // Convert 24-hour to 12-hour
        let hour12 = hours24 % 12;
        if (hour12 === 0) hour12 = 12;
        const period = hours24 >= 12 ? 'pm' : 'am';
        console.log('[DEBUG] loadSettingsPage: Converted to 12-hour:', { hour12, period });
        
        hourSelect.value = String(hour12).padStart(2, '0');
        const minuteVal = (parseInt(minutes, 10) - (parseInt(minutes, 10) % 5)).toString().padStart(2, '0');
        minuteSelect.value = minuteVal;
        periodSelect.value = period;
        console.log('[DEBUG] loadSettingsPage: Set UI values - hour:', hourSelect.value, 'minute:', minuteSelect.value, 'period:', periodSelect.value);
    }
    
    loadUpdateSettings();
    loadAccountSettings();
}

// Load settings from server
async function loadSettingsLegacy() {
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings');
        const settings = await response.json();

        // Update UI elements
        if (settings.autostart !== undefined) {
            document.getElementById('autostart-toggle').checked = settings.autostart;
        }
        if (settings.autosave_interval !== undefined) {
            document.getElementById('autosave-interval').value = settings.autosave_interval;
        }
        if (settings.daily_reset_time !== undefined) {
            document.getElementById('daily-reset-time').value = settings.daily_reset_time;
        }
        if (settings.theme !== undefined) {
            document.getElementById('theme-selector').value = settings.theme;
        }
        if (settings.finish !== undefined) {
            document.getElementById('finish-selector').value = settings.finish;
        }
        if (settings.intensity !== undefined) {
            document.getElementById('intensity-selector').value = settings.intensity;
        }
        if (settings.dpi_scale !== undefined) {
            document.getElementById('dpi-selector').value = settings.dpi_scale;
        }
    } catch (error) {
        Utils.Logger.error('Failed to load settings:', error);
    }
}

// Load update settings
async function loadUpdateSettings() {
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/updates');
        const settings = await response.json();

        if (settings.channel !== undefined) {
            document.getElementById('update-channel').value = settings.channel;
        }
        if (settings.auto_update !== undefined) {
            document.getElementById('auto-update-check').checked = settings.auto_update;
        }
        if (settings.auto_install !== undefined) {
            document.getElementById('auto-update-install').checked = settings.auto_install;
        }
        if (settings.backup_before_update !== undefined) {
            document.getElementById('backup-before-update').checked = settings.backup_before_update;
        }
        if (settings.github_auto_update !== undefined) {
            document.getElementById('github-auto-update').checked = settings.github_auto_update;
        }
        if (settings.github_branch !== undefined) {
            document.getElementById('github-branch').value = settings.github_branch;
        }
        if (settings.check_interval !== undefined) {
            document.getElementById('check-interval').value = settings.check_interval;
        }
        if (settings.backup_enabled !== undefined) {
            document.getElementById('backup-toggle').checked = settings.backup_enabled;
        }
    } catch (error) {
        Utils.Logger.error('Failed to load update settings:', error);
    }
}

// Load account settings
async function loadAccountSettings() {
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/account');
        
        // Account endpoint doesn't exist yet - gracefully handle
        if (!response.ok) {
            console.log('Account endpoint not available (expected)');
            return;
        }
        
        const account = await response.json();

        // Update UI elements
        if (account.username) {
            document.getElementById('account-username').textContent = account.username;
        }
        if (account.created_at) {
            document.getElementById('account-created').textContent = Utils.formatDate(account.created_at);
        }
        if (account.last_login) {
            document.getElementById('account-last-login').textContent = Utils.formatDate(account.last_login);
        }
    } catch (error) {
        // Account endpoint not implemented yet - suppress error
        console.log('Account settings not available (endpoint not implemented)');
    }
}

// Theme and DPI Functions

// Setup daily reset
function setupDailyReset() {
    // Cancel existing timer
    const existingTimer = AppState.get('dailyResetTimer');
    if (existingTimer) {
        clearTimeout(existingTimer);
    }

    // Setup new timer
    const settings = AppState.get('currentSettings') || {};
    const resetTime = settings.daily_reset_time || '08:00';

    const [hours, minutes] = resetTime.split(':');
    const now = new Date();
    const resetToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), parseInt(hours), parseInt(minutes));

    let timeUntilReset;
    if (resetToday > now) {
        timeUntilReset = resetToday - now;
    } else {
        // Reset tomorrow
        const resetTomorrow = new Date(resetToday);
        resetTomorrow.setDate(resetTomorrow.getDate() + 1);
        timeUntilReset = resetTomorrow - now;
    }

    const timer = setTimeout(() => {
        // Perform daily reset
        console.log('Performing daily reset');
        resetDailyStrikes();

        // Setup next reset
        setupDailyReset();
    }, timeUntilReset);

    AppState.set('dailyResetTimer', timer);
    Utils.Logger.info(`Daily reset scheduled for ${resetTime}`);
}

// Reset daily strikes
async function resetDailyStrikes() {
    // This function resets daily strike flags and performs schedule cleanup
    console.log('Resetting daily strikes');
    try {
        const resp = await apiCall('/api/tasks/reset-daily-strikes', { method: 'POST' });
        const data = await resp.json();
        if (data && data.success) {
            console.log('Daily strikes reset successfully');
            // Reload tasks using the Tasks module to avoid stale merges
            try {
                if (typeof loadTasks === 'function') {
                    await loadTasks();
                }
            } catch (e) { 
                console.warn('Error loading tasks:', e);
            }
            
            // Force re-render of tasks with a slight delay to ensure data is loaded
            // Use setTimeout to allow DOM updates to complete
            setTimeout(() => {
                try {
                    // Reset filter to 'active' to show newly unstiked tasks
                    const currentPage = (AppState && AppState.get) ? AppState.get('currentPage') : 'tasks';
                    
                    // If on tasks page, ensure 'active' filter is applied to show reset tasks
                    if (currentPage === 'tasks') {
                        AppState.set('currentFilter', 'active');
                        if (typeof renderTasks === 'function') {
                            renderTasks();
                        }
                        // Update filter tab UI to show 'active' is selected
                        const filterTabs = document.querySelectorAll('.filter-tab');
                        filterTabs.forEach(tab => {
                            tab.classList.remove('active');
                            if (tab.getAttribute('data-filter') === 'active') {
                                tab.classList.add('active');
                            }
                        });
                    }
                } catch (e) { 
                    console.warn('Error re-rendering tasks after reset:', e);
                }
            }, 100);
            
            // Update stats immediately
            try { if (typeof updateDashboardStats === 'function') updateDashboardStats(); } catch(e) {}
            // Clean up overdue (previous-day) scheduled tasks at reset time
            try {
                await apiCall('/api/planner-v2/cleanup-overdue', { method: 'POST' });
            } catch (e) { console.warn('Cleanup-overdue failed:', e); }
            // Refresh planner and navbar schedule card
            try { if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.refresh === 'function') { window.DailyPlannerV2.refresh(); } } catch(e) {}
            try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.update === 'function') { window.NavbarScheduleCard.update(); } } catch(e) {}
        } else {
            console.error('Failed to reset daily strikes:', data && data.error);
        }
    } catch (error) {
        console.error('Error during reset/cleanup:', error);
    }
}

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
        const tag = (e.target && e.target.tagName || '').toLowerCase();
        const isTypingTarget = tag === 'input' || tag === 'textarea' || (e.target && e.target.isContentEditable);

        // Plain "P" opens Notes page when not typing in a field
        if (!e.ctrlKey && !e.metaKey && !e.altKey && (e.key === 'p' || e.key === 'P') && !isTypingTarget) {
            e.preventDefault();
            navigateToPage('notes');
            return;
        }

        // Ctrl/Cmd + N - New task
        if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
            e.preventDefault();
            Tasks.openQuickAddModal();
        }

        // Ctrl/Cmd + S - Save current task
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            const editingTaskId = AppState.get('editingTaskId');
            if (editingTaskId) {
                Tasks.saveTask();
            }
        }

        // Escape - Close modals
        if (e.key === 'Escape') {
            // Close any open modals
            Tasks.closeTaskModal();
            Tasks.closeQuickAddModal();
            Tasks.closeStrikeModal();
            closePasswordModal();
            closeBackupModal();
            closeUpdateModal();
            closeLogsModal();
        }
    });
}

// Changelog functions
async function loadChangelog() {
    try {
        const response = await fetch('/api/changelog');
        if (response.ok) {
            const changelogText = await response.text();
            return changelogText;
        } else {
            throw new Error('Failed to load changelog');
        }
    } catch (error) {
        Utils.Logger.error('Failed to load changelog:', error);
        return 'Error loading changelog. Please check your connection and try again.';
    }
}

function parseChangelogToSections(markdown) {
    // Parse the changelog markdown into version sections (including consolidated ranges),
    // then group by major version.
    const sections = [];
    const lines = markdown.split('\n');
    let currentSection = null;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // Check for single-version headers (## Version X.X)
        if (line.startsWith('## Version ')) {
            if (currentSection) {
                sections.push(currentSection);
            }
            currentSection = {
                version: line.replace('## Version ', '').split(' - ')[0],
                title: line.replace('## ', ''),
                content: [],
                date: null,
                versionRange: null
            };
        }
        // Check for consolidated range headers (## Versions 11.0 – 12.1 – ...)
        else if (line.startsWith('## Versions ')) {
            if (currentSection) {
                sections.push(currentSection);
            }
            const headerRest = line.replace('## Versions ', '');
            const versionMatches = headerRest.match(/(\d+\.\d+)/g) || [];
            // Use the last numeric token as the synthetic version for sorting (e.g. 12.1)
            const syntheticVersion = versionMatches.length
                ? versionMatches[versionMatches.length - 1]
                : headerRest.split(' - ')[0].trim();

            let versionRange = null;
            if (versionMatches.length >= 2) {
                const startMajor = parseInt(versionMatches[0].split('.')[0], 10);
                const endMajor = parseInt(versionMatches[versionMatches.length - 1].split('.')[0], 10);
                if (Number.isFinite(startMajor) && Number.isFinite(endMajor)) {
                    versionRange = { startMajor, endMajor };
                }
            }

            currentSection = {
                version: syntheticVersion,
                title: line.replace('## ', ''),
                content: [],
                date: null,
                versionRange
            };
        }
        // Check for release date
        else if (line.startsWith('Release Date:') && currentSection) {
            currentSection.date = line.replace('Release Date:', '').trim();
        }
        // Add content to current section (skip blank lines outside sections)
        else if (currentSection && line) {
            currentSection.content.push(line);
        }
    }
    
    // Add the last section
    if (currentSection) {
        sections.push(currentSection);
    }
    
    // Helper to compare two version strings (semver-ish)
    function compareVersions(a, b) {
        const va = (a || '').split('.').map(Number);
        const vb = (b || '').split('.').map(Number);
        const maxLen = Math.max(va.length, vb.length);
        for (let i = 0; i < maxLen; i++) {
            const na = va[i] || 0;
            const nb = vb[i] || 0;
            if (na !== nb) return na - nb;
        }
        return 0;
    }
    
    // Sort by version (latest first) - simple version comparison
    sections.sort((a, b) => compareVersions(b.version, a.version));
    
    // Group sections by major version (e.g. 13.7, 13.6 → major "13").
    // Consolidated range sections (with versionRange) are attached to every
    // major they cover (e.g. 11 and 12 for "Versions 11.0 – 12.1").
    const groupsMap = new Map();

    sections.forEach(section => {
        if (section.versionRange) {
            const { startMajor, endMajor } = section.versionRange;
            if (Number.isFinite(startMajor) && Number.isFinite(endMajor)) {
                for (let majorNum = startMajor; majorNum <= endMajor; majorNum++) {
                    const majorKey = String(majorNum);
                    if (!groupsMap.has(majorKey)) {
                        groupsMap.set(majorKey, {
                            majorVersion: majorKey,
                            sections: []
                        });
                    }
                    groupsMap.get(majorKey).sections.push(section);
                }
                return;
            }
        }

        const rawVersion = section.version || '';
        const major = (rawVersion.split('.')[0] || rawVersion || '0').trim();
        if (!groupsMap.has(major)) {
            groupsMap.set(major, {
                majorVersion: major,
                sections: []
            });
        }
        groupsMap.get(major).sections.push(section);
    });

    // Sort sections within each major group (latest minor first)
    groupsMap.forEach(group => {
        group.sections.sort((a, b) => compareVersions(b.version, a.version));
    });

    // Convert to an array of groups sorted by major version (latest first)
    const groups = Array.from(groupsMap.values()).sort((a, b) => {
        const ma = parseInt(a.majorVersion, 10) || 0;
        const mb = parseInt(b.majorVersion, 10) || 0;
        return mb - ma;
    });

    return groups;
}

function splitHighlightsAndBody(contentLines) {
    // Derive short "quick highlights" for the version while
    // keeping the full content intact for detailed rendering.
    const body = Array.isArray(contentLines) ? contentLines : [];
    const quick = [];

    if (!body.length) {
        return { highlights: quick, body };
    }

    const lines = body;

    function collectBullets(startIndex) {
        const items = [];
        for (let i = startIndex; i < lines.length; i++) {
            const t = lines[i].trim();
            if (!t || (!t.startsWith('- ') && !t.startsWith('* '))) {
                break;
            }
            const text = t.replace(/^[-*]\s+/, '');
            items.push(text);
        }
        return items;
    }

    // Helper to shorten a bullet to maxWords words.
    function shorten(text, maxWords) {
        const words = text.split(/\s+/).filter(Boolean);
        if (words.length <= maxWords) {
            return text;
        }
        return words.slice(0, maxWords).join(' ') + '…';
    }

    // Pass 1: explicit "Quick Highlights" heading
    for (let i = 0; i < lines.length; i++) {
        const trimmed = lines[i].trim();
        if (/^quick highlights$/i.test(trimmed)) {
            const items = collectBullets(i + 1);
            if (items.length) {
                items.forEach(item => quick.push(shorten(item, 7)));
            }
            return { highlights: quick, body };
        }
    }

    // Pass 2: explicit "Highlights" / "Consolidated Highlights" heading
    for (let i = 0; i < lines.length && quick.length === 0; i++) {
        const trimmed = lines[i].trim();
        if (/^highlights$/i.test(trimmed) || /^consolidated highlights$/i.test(trimmed)) {
            const items = collectBullets(i + 1);
            if (items.length) {
                items.forEach(item => quick.push(shorten(item, 7)));
            }
        }
    }

    // Pass 3: fallback to first bullet list anywhere near the top
    if (!quick.length) {
        for (let i = 0; i < lines.length; i++) {
            const trimmed = lines[i].trim();
            if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
                const items = collectBullets(i);
                if (items.length) {
                    items.forEach(item => quick.push(shorten(item, 7)));
                }
                break;
            }
        }
    }

    return { highlights: quick, body };
}

function formatChangelogSections(groups) {
    let html = '<div class="changelog-sections">';
    
    groups.forEach((group, index) => {
        const isExpanded = index === 0; // Expand latest major version by default
        const sectionId = `changelog-section-${group.majorVersion}`;

        // Derive a simple date range for the group if dates are present
        const dates = group.sections
            .map(s => s.date)
            .filter(Boolean)
            .sort(); // ascending
        let dateLabel = '';
        if (dates.length === 1) {
            dateLabel = dates[0];
        } else if (dates.length > 1) {
            const first = dates[0];
            const last = dates[dates.length - 1];
            dateLabel = `${first} – ${last}`;
        }

        html += `
            <div class="changelog-section">
                <div class="changelog-section-header" onclick="toggleChangelogSection('${sectionId}')">
                    <div class="changelog-section-title">
                        <h3>Version ${group.majorVersion}.x</h3>
                        ${dateLabel ? `<span class="changelog-date">${dateLabel}</span>` : ''}
                    </div>
                    <div class="changelog-section-toggle">
                        <i class="fas fa-chevron-${isExpanded ? 'up' : 'down'}"></i>
                    </div>
                </div>
                <div class="changelog-section-content ${isExpanded ? 'expanded' : ''}" id="${sectionId}">
                    <div class="changelog-section-text">
                        ${group.sections.map(section => {
                            const split = splitHighlightsAndBody(section.content || []);
const highlightsHtml = split.highlights.length
                                ? `
                                    <div class="changelog-highlights">
                                        <div class="changelog-highlights-title">Quick Highlights</div>
                                        <ul>
                                            ${split.highlights.map(item => `<li>${item}</li>`).join('')}
                                        </ul>
                                    </div>
                                  `
                                : '';
                            const bodyHtml = formatChangelogContent(split.body || []);
                            return `
                                <div class="changelog-subsection">
                                    <h4>${section.title}</h4>
                                    ${section.date ? `<div class="changelog-date changelog-date-sub">${section.date}</div>` : ''}
                                    ${highlightsHtml}
                                    ${bodyHtml}
                                </div>
                            `;
                        }).join('')}
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    return html;
}

function formatChangelogContent(contentLines) {
    let html = '';
    let inCodeBlock = false;
    let codeBlockContent = '';
    
    for (const line of contentLines) {
        if (line.startsWith('```')) {
            if (inCodeBlock) {
                // End code block
                html += `<pre><code>${codeBlockContent}</code></pre>`;
                codeBlockContent = '';
                inCodeBlock = false;
            } else {
                // Start code block
                inCodeBlock = true;
            }
        } else if (inCodeBlock) {
            codeBlockContent += line + '\n';
        } else if (line.startsWith('### ')) {
            html += `<h4>${line.replace('### ', '')}</h4>`;
        } else if (line.startsWith('## ')) {
            html += `<h3>${line.replace('## ', '')}</h3>`;
        } else if (line.startsWith('# ')) {
            html += `<h2>${line.replace('# ', '')}</h2>`;
        } else if (line.startsWith('- **')) {
            // Bold list item
            const boldText = line.match(/\*\*(.*?)\*\*/);
            if (boldText) {
                html += `<li><strong>${boldText[1]}</strong>${line.replace(/- \*\*.*?\*\*/, '').trim()}</li>`;
            } else {
                html += `<li>${line.replace('- ', '')}</li>`;
            }
        } else if (line.startsWith('- ')) {
            html += `<li>${line.replace('- ', '')}</li>`;
        } else if (line.startsWith('**') && line.endsWith('**')) {
            html += `<strong>${line.replace(/\*\*/g, '')}</strong>`;
        } else if (line.trim() === '---') {
            html += '<hr>';
        } else if (line.trim()) {
            html += `<p>${line}</p>`;
        }
    }
    
    // Close any remaining code block
    if (inCodeBlock && codeBlockContent) {
        html += `<pre><code>${codeBlockContent}</code></pre>`;
    }
    
    return html;
}

function toggleChangelogSection(sectionId) {
    const content = document.getElementById(sectionId);
    const header = content.previousElementSibling;
    const toggle = header.querySelector('.changelog-section-toggle i');
    
    if (content.classList.contains('expanded')) {
        content.classList.remove('expanded');
        toggle.className = 'fas fa-chevron-down';
    } else {
        content.classList.add('expanded');
        toggle.className = 'fas fa-chevron-up';
    }
}

async function openChangelogModal() {
    const modal = document.getElementById('changelog-modal');
    const content = document.getElementById('changelog-content');

    // Show loading state
    content.innerHTML = `
        <div class="loading-changelog">
            <div class="loading-spinner"></div>
            <p>Loading changelog...</p>
        </div>
    `;

    modal.classList.add('active');
    modal.style.display = 'flex';

    try {
        const changelogText = await loadChangelog();
        const sections = parseChangelogToSections(changelogText);
        const formattedChangelog = formatChangelogSections(sections);

        content.innerHTML = formattedChangelog;
    } catch (error) {
        content.innerHTML = `
            <div class="changelog-content">
                <div style="text-align: center; padding: 2rem; color: var(--text-secondary);">
                    <i class="fas fa-exclamation-triangle" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                    <h3>Unable to Load Changelog</h3>
                    <p>There was an error loading the changelog. Please check your connection and try again.</p>
                </div>
            </div>
        `;
    }
}

function closeChangelogModal() {
    const modal = document.getElementById('changelog-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
}

async function maybeShowWhatsNewModal() {
    try {
        const currentVersion = (window.APP_CONFIG && window.APP_CONFIG.version) || null;
        if (!currentVersion) {
            return;
        }

        const storageKey = 'shakshuka_last_seen_version';
        const lastSeen = localStorage.getItem(storageKey);

        // Only show if the stored version is different from the current version
        if (lastSeen === currentVersion) {
            return;
        }

        // Fetch changelog and extract highlights for the latest version
        const changelogText = await loadChangelog();
        const groups = parseChangelogToSections(changelogText);
        if (!Array.isArray(groups) || groups.length === 0) {
            localStorage.setItem(storageKey, currentVersion);
            return;
        }

        const latestGroup = groups[0];
        const latestSection = latestGroup.sections && latestGroup.sections[0];
        if (!latestSection) {
            localStorage.setItem(storageKey, currentVersion);
            return;
        }

        const split = splitHighlightsAndBody(latestSection.content || []);
        const summaryEl = document.getElementById('whats-new-summary');
        if (!summaryEl) {
            localStorage.setItem(storageKey, currentVersion);
            return;
        }

        if (split.highlights.length) {
            summaryEl.innerHTML = `
                <ul>
                    ${split.highlights.map(item => `<li>${item}</li>`).join('')}
                </ul>
            `;
        } else {
            // Fallback: show first few lines of body as plain text
            const preview = (latestSection.content || []).slice(0, 5).join(' ');
            summaryEl.textContent = preview || 'This update includes stability improvements and minor fixes.';
        }

        const modal = document.getElementById('whats-new-modal');
        if (!modal) {
            localStorage.setItem(storageKey, currentVersion);
            return;
        }

        modal.classList.add('active');
        modal.style.display = 'flex';

        const dismiss = document.getElementById('whats-new-dismiss-btn');
        const closeBtn = document.getElementById('close-whats-new-modal');
        const viewChangelog = document.getElementById('whats-new-view-changelog-btn');

        const closeWhatsNew = () => {
            modal.classList.remove('active');
            modal.style.display = 'none';
            localStorage.setItem(storageKey, currentVersion);
        };

        if (dismiss) dismiss.onclick = closeWhatsNew;
        if (closeBtn) closeBtn.onclick = closeWhatsNew;
        if (viewChangelog) {
            viewChangelog.onclick = async () => {
                closeWhatsNew();
                await openChangelogModal();
            };
        }
    } catch (e) {
        // If anything goes wrong, just mark the current version as seen so we don't spam.
        try {
            const currentVersion = (window.APP_CONFIG && window.APP_CONFIG.version) || null;
            if (currentVersion) {
                localStorage.setItem('shakshuka_last_seen_version', currentVersion);
            }
        } catch (_) {}
    }
}

// Global functions that use AppState - no global variables needed

// Note: CSRF/notification/helpers are provided by utils.js; duplicates removed here to avoid conflicts.

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


// Authentication is disabled - no modal needed

// Authentication is disabled - no modal functions needed

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
    if (typeof updateDashboardStats === 'function') updateDashboardStats();
    // Initialize planner v2 if user lands on planner later
    if (typeof window.ensurePlannerV2Init === 'function' && AppState.get('currentPage') === 'planner') {
        window.ensurePlannerV2Init();
    }
    applyThemeAndDPI();
    setupDailyReset();
    setupKeyboardShortcuts();
    initializeLogging();
    
    // If we're on the planner page, make sure it's loaded
    const currentPage = AppState.get('currentPage');
    console.log('Current page after loadAppData:', currentPage);
    if (currentPage === 'planner') {
        console.log('Loading planner v2 after app data load');
        if (typeof window.ensurePlannerV2Init === 'function') {
            window.ensurePlannerV2Init();
        }
    }
}

function clearLogs() {
    AppState.set('developerLogs', []);
    displayLogs();
    addLog('info', 'Logs cleared');
}

// Initialize the application
function initializeApp() {
    if (typeof updateDashboardStats === 'function') updateDashboardStats();
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

    // Navigation - only add listeners if not already added
    console.log('Setting up navigation event listeners...');
    document.querySelectorAll('.nav-item').forEach(item => {
        // Check if listener already added
        if (item.dataset.listenerAdded === 'true') {
            console.log('Listener already added to nav item:', item);
            return;
        }
        console.log('Adding click listener to nav item:', item);
        item.dataset.listenerAdded = 'true';
        item.addEventListener('click', function() {
            console.log('Nav item clicked:', this);
            const page = this.dataset.page;
            console.log('Navigating to page:', page);
            navigateToPage(page);
        });
    });
    console.log('Navigation event listeners set up complete');

    // Task modals
    safeAddEventListener('quick-add-btn', 'click', () => openQuickAddModal());
    
    // Modal controls
    safeAddEventListener('close-modal', 'click', () => closeTaskModal());
    safeAddEventListener('close-quick-modal', 'click', () => closeQuickAddModal());
    safeAddEventListener('cancel-task', 'click', () => closeTaskModal());
    safeAddEventListener('cancel-quick-task', 'click', () => closeQuickAddModal());
    
    // Form submissions
    safeAddEventListener('save-task', 'click', () => saveTask());
    safeAddEventListener('save-quick-task', 'click', () => saveQuickTask());
    
    // Inline quick add
    safeAddEventListener('inline-quick-add', 'keydown', async (e) => {
        if (e.key === 'Enter') {
            const input = e.target;
            const title = (input.value || '').trim();
            const err = document.getElementById('inline-quick-error');
            if (!title) {
                if (err) { err.style.display = 'flex'; err.querySelector('.msg').textContent = 'Please enter a task title'; }
                return;
            }
            try {
                if (err) err.style.display = 'none';
                let taskPayload = { title, description: '', project: '', estimated_duration: 60 };
                // Inline quick-add should also respect quick project-from-title when enabled
                taskPayload = applyQuickProjectFromTitle(taskPayload);

                await createTask(taskPayload);
                input.value = '';
                // Refresh UI depending on current page
                const page = AppState.get('currentPage');
                if (page === 'tasks') {
                    renderTasks();
                } else if (page === 'planner') {
                    try {
                        if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.loadAvailableTasks === 'function') {
                            window.DailyPlannerV2.loadAvailableTasks();
                        }
                    } catch (e) { /* no-op */ }
                }
            } catch (ex) {
                if (err) { err.style.display = 'flex'; err.querySelector('.msg').textContent = ex.message || 'Failed to add task'; }
            }
        }
    });

    // Changelog functionality
    safeAddEventListener('view-changelog-btn', 'click', () => openChangelogModal());
    safeAddEventListener('close-changelog-modal', 'click', () => closeChangelogModal());
    
    // User session management
    safeAddEventListener('reset-session-btn', 'click', () => {
        if (confirm('This will reset your user session and you will get a new user ID. All your current data will be lost. Are you sure?')) {
            Auth.resetUserSession();
        }
    });
    
    // Filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', function() {
            const filter = this.dataset.filter;
            setActiveFilter(filter);
            filterTasks(filter);
        });
    });

    // Date navigation (legacy planner only). If Planner v2 is present, it owns these.
    if (typeof window.ensurePlannerV2Init !== 'function') {
        safeAddEventListener('prev-day', 'click', () => changeDate(-1));
        safeAddEventListener('next-day', 'click', () => changeDate(1));
    }

    // Settings
    safeAddEventListener('autostart-toggle', 'change', updateAutostart);
    safeAddEventListener('autosave-interval', 'change', updateAutosaveInterval);
    safeAddEventListener('quick-project-from-title', 'change', updateQuickProjectFromTitle);
    safeAddEventListener('casual-dates-toggle', 'change', updateCasualDates);
    safeAddEventListener('daily-reset-time', 'change', updateDailyResetTime);
    safeAddEventListener('theme-selector', 'change', updateTheme);
    safeAddEventListener('finish-selector', 'change', updateFinish);
    safeAddEventListener('intensity-selector', 'change', updateIntensity);
    safeAddEventListener('dpi-selector', 'change', updateDPI);
    // Navbar planner style toggle (stored locally)
    safeAddEventListener('navbar-planner-style', 'change', () => {
        const el = document.getElementById('navbar-planner-style');
        const val = el ? el.value : 'clean';
        try { if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.setStyle === 'function') { window.NavbarScheduleCard.setStyle(val); } } catch(e) {}
    });
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

    // Fallback: delegate strike button clicks to handle cases where inline handlers fail after navigation
    if (!window.__strikeDelegationSetup) {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.task-action.strike-btn, .task-action[title="Strike Task"], .task-actions .task-action');
            if (!btn) return;
            // Only consider buttons with a check icon or Strike title
            const hasCheckIcon = !!btn.querySelector('.fa-check');
            const isStrikeTitled = (btn.getAttribute('title') || '').toLowerCase().includes('strike');
            if (!hasCheckIcon && !isStrikeTitled) return;
            if (btn.classList.contains('disabled')) return;
            const taskContainer = btn.closest('[data-task-id]');
            const taskId = taskContainer ? taskContainer.getAttribute('data-task-id') : null;
            if (!taskId) return;
            if (typeof openStrikeModal === 'function') {
                openStrikeModal(taskId);
            } else if (window.Tasks && typeof window.Tasks.openStrikeModal === 'function') {
                window.Tasks.openStrikeModal(taskId);
            }
        });
        window.__strikeDelegationSetup = true;
    }

    // Schedule/Quick Add button on planner header
    safeAddEventListener('add-task-to-planner', 'click', () => openQuickAddModal());
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
    safeAddEventListener('cancel-update', 'click', cancelOrCloseUpdateModal);
    safeAddEventListener('download-update', 'click', downloadAndInstallUpdate);
    
    // Update and backup buttons
    safeAddEventListener('check-updates-btn', 'click', checkForUpdates);
    safeAddEventListener('github-update-btn', 'click', checkGitHubUpdate);
    safeAddEventListener('create-backup-btn', 'click', createBackup);
    
    // GitHub update modal
    safeAddEventListener('close-github-update-modal', 'click', closeGitHubUpdateModal);
    safeAddEventListener('cancel-github-update', 'click', closeGitHubUpdateModal);
    safeAddEventListener('download-github-update', 'click', downloadGitHubUpdate);
    
    // Update settings
    safeAddEventListener('auto-update-check', 'change', updateUpdateSettings);
    safeAddEventListener('auto-update-install', 'change', updateUpdateSettings);
    safeAddEventListener('backup-before-update', 'change', updateUpdateSettings);
    safeAddEventListener('github-auto-update', 'change', updateUpdateSettings);
    safeAddEventListener('github-branch', 'change', updateUpdateSettings);
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
            if (e.target !== this) return; // only when clicking the backdrop itself

            const id = this.id;

            // Prefer dedicated close functions so each modal can clean up its own state
            if (id === 'task-modal' && typeof closeTaskModal === 'function') {
                closeTaskModal();
                return;
            }
            if (id === 'quick-add-modal' && typeof closeQuickAddModal === 'function') {
                closeQuickAddModal();
                return;
            }
            if (id === 'strike-modal' && typeof closeStrikeModal === 'function') {
                closeStrikeModal();
                return;
            }
            if (id === 'schedule-modal' && typeof closeScheduleModal === 'function') {
                closeScheduleModal();
                return;
            }
            if (id === 'logs-modal' && typeof closeLogsModal === 'function') {
                closeLogsModal();
                return;
            }
            if (id === 'backup-modal' && typeof closeBackupModal === 'function') {
                closeBackupModal();
                return;
            }
            if (id === 'update-modal' && typeof closeUpdateModal === 'function') {
                closeUpdateModal();
                return;
            }
            if (id === 'import-modal' && typeof closeImportModal === 'function') {
                closeImportModal();
                return;
            }
            if (id === 'changelog-modal' && typeof closeChangelogModal === 'function') {
                closeChangelogModal();
                return;
            }
            if (id === 'github-update-modal' && typeof closeGitHubUpdateModal === 'function') {
                closeGitHubUpdateModal();
                return;
            }

            // Fallback: hide any other modal by removing the active class
            // and clearing the inline display style so it fully closes.
            this.classList.remove('active');
            this.style.display = 'none';
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
    
    if (page === 'import') {
        // Import - don't navigate, just open import modal
        openImportModal();
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
    if (page === 'analytics') {
        updateDashboardStats();
    } else if (page === 'settings') {
        loadSettingsPage();
    } else if (page === 'planner') {
        // Prefer Planner v2 if available
        if (typeof window.ensurePlannerV2Init === 'function') {
            window.ensurePlannerV2Init();
        } else if (typeof loadPlannerData === 'function') {
            // Fallback to legacy planner only if v2 is not present
            loadPlannerData();
        }
    } else if (page === 'tasks') {
        // Ensure freshest data when navigating to Tasks
        try {
            if (window.Tasks && typeof window.Tasks.loadTasks === 'function') {
                window.Tasks.loadTasks();
            } else if (typeof loadTasks === 'function') {
                loadTasks();
            }
        } catch (e) { /* fallback render below */ }
        // Also preserve filter and trigger render immediately
        try {
            const currentFilter = (typeof AppState !== 'undefined' && AppState.get) ? AppState.get('currentFilter') : 'active';
            if (typeof setActiveFilter === 'function') setActiveFilter(currentFilter);
            renderTasks(currentFilter);
        } catch (e) {
            renderTasks();
        }
    }
}

// Missing navigation functions
function toggleSidebar() {
    console.log('Toggle sidebar called');
    const sidebar = document.querySelector('.sidebar');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
        console.log('Sidebar toggled');
    } else {
        console.error('Sidebar element not found');
    }
}

function killApp() {
    console.log('Kill app called');
    if (confirm('Are you sure you want to stop the Shakshuka server?')) {
        // Send request to kill the app
        fetch('/api/kill', { method: 'POST' })
            .then(() => {
                console.log('App kill request sent');
                window.close();
            })
            .catch(error => {
                console.error('Error killing app:', error);
                // Fallback: just close the window
                window.close();
            });
    }
}

// Missing utility functions
function showLoading(show) {
    const loadingElement = document.getElementById('loading-screen');
    if (loadingElement) {
        if (show) {
            loadingElement.style.display = 'flex';
        } else {
            loadingElement.style.display = 'none';
        }
    }
}

// Task Management
async function loadTasks() {
    // Delegate to Tasks module when available to ensure consistent merging logic
    try {
        if (window.Tasks && typeof window.Tasks.loadTasks === 'function' && window.Tasks.loadTasks !== loadTasks) {
            return window.Tasks.loadTasks();
        }
    } catch (e) { /* fallback to local implementation below */ }

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
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const baseData = await response.json();
            let merged = Array.isArray(baseData) ? baseData : [];

            // Merge scheduled tasks from Planner v2 so Tasks page shows them too
            try {
                const schedResp = await fetch('/api/planner-v2/schedule');
                if (schedResp.ok) {
                    const schedData = await schedResp.json();
                    if (schedData && schedData.success && schedData.scheduled_tasks) {
                        const flatScheduled = [];
                        Object.values(schedData.scheduled_tasks).forEach(dayMap => {
                            Object.values(dayMap).forEach(hourTasks => {
                                hourTasks.forEach(t => flatScheduled.push(t));
                            });
                        });
                        const map = new Map();
                        merged.forEach(t => map.set(t.id, t));
                        flatScheduled.forEach(t => map.set(t.id, t));
                        merged = Array.from(map.values());
                    }
                }
            } catch (e) {
                // ignore if planner-v2 endpoint not available
            }

            AppState.setTasks(merged);
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks(AppState.get('currentFilter'));
            } else if (AppState.get('currentPage') === 'analytics') {
                renderRecentTasks();
            } else if (AppState.get('currentPage') === 'planner') {
                // Use Planner v2 when available to avoid duplicate legacy work
                if (typeof window.ensurePlannerV2Init === 'function') {
                    window.ensurePlannerV2Init();
                } else if (typeof loadPlannerData === 'function') {
                    loadPlannerData(); // Legacy fallback
                }
            }
            
            updateDashboardStats();
            Utils.Logger.log(`Loaded ${AppState.getTasks().length} tasks`);
            showLoading(false); // Hide loading overlay on success
            return; // Success
            
        } catch (error) {
            // Only log final failure to reduce console spam
            if (attempt === MAX_RETRIES) {
                Utils.Logger.error(`Load tasks failed after ${MAX_RETRIES} attempts:`, error);
            }
            
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

// Task Rendering (uses requestAnimationFrame for smoother DOM updates)
let _renderTasksRafId = null;

// Use rAF when available; fallback to a 1s timeout if browser is throttled or rAF is missing
const _renderTasksSchedule = (cb) => {
    const raf = window.requestAnimationFrame;
    if (typeof raf === 'function') {
        return raf(cb);
    }
    return setTimeout(cb, 1000); // 1 second fallback
};

function _renderTasksNow(filter, projectFilterArg) {
    const tasksList = document.getElementById('tasks-list');

    const projectFilter = (typeof projectFilterArg !== 'undefined' && projectFilterArg !== null)
        ? projectFilterArg
        : ((typeof AppState !== 'undefined' && AppState.get) ? AppState.get('projectFilter') || 'all' : 'all');
    
    console.log('renderTasks called with:', {
        filter,
        projectFilter,
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
    
    // First apply status filter, then project filter
    const statusFiltered = filterTasksByType(tasks, filter);

    let filteredTasks = statusFiltered;
    if (projectFilter && projectFilter !== 'all') {
        filteredTasks = statusFiltered.filter(task => {
            const name = (task.project || '').trim();
            if (projectFilter === '__none__') {
                return !name;
            }
            return name === projectFilter;
        });
    }

    console.log('Filtered tasks:', filteredTasks.length, filteredTasks);
    
    // Sort tasks: active tasks first, then struck tasks, and group tasks due today
    const todayStr = new Date().toISOString().split('T')[0];
    const sortedTasks = filteredTasks.sort((a, b) => {
        // First, handle struck_today so completed/struck tasks fall to the bottom
        if (a.struck_today && b.struck_today) return 0;
        if (a.struck_today && !b.struck_today) return 1;
        if (!a.struck_today && b.struck_today) return -1;

        // Within the same struck status, move tasks due today to the front of the queue
        const aDueToday = !a.struck_today && a.due_date && String(a.due_date).split('T')[0] === todayStr;
        const bDueToday = !b.struck_today && b.due_date && String(b.due_date).split('T')[0] === todayStr;

        if (aDueToday && !bDueToday) return -1;
        if (!aDueToday && bDueToday) return 1;

        // Otherwise, keep original relative order
        return 0;
    });
    
    if (sortedTasks.length === 0) {
        // Customize empty state message based on current filter
        let emptyMessage = 'No tasks found';
        let emptyDescription = 'Create your first task to get started!';
        let emptyIcon = 'fa-tasks';
        
        if (filter === 'expired') {
            emptyMessage = 'Yay! No missed tasks';
            emptyDescription = 'All your tasks are on track!';
            emptyIcon = 'fa-check-circle';
        } else if (filter === 'active') {
            emptyMessage = 'No active tasks';
            emptyDescription = 'Create a new task to get started!';
            emptyIcon = 'fa-inbox';
        } else if (filter === 'completed') {
            emptyMessage = 'No completed tasks';
            emptyDescription = 'Get to work and complete some tasks!';
            emptyIcon = 'fa-clipboard-list';
        }
        
        tasksList.innerHTML = `
            <div class="empty-state">
                <i class="fas ${emptyIcon}" style="font-size: 3rem; color: #FFB6C1; margin-bottom: 1rem;"></i>
                <h3>${emptyMessage}</h3>
                <p>${emptyDescription}</p>
            </div>
        `;
        return;
    }

    if (AppState.get('currentLayout') === 'grid') {
        Utils.Logger.log('Rendering grid layout with', sortedTasks.length, 'tasks');
        const gridHTML = `
            <div class="tasks-grid">
                ${sortedTasks.map(task => {
                    const maxStrikes = 8;
                    const currentStrikes = task.strike_count || 0;
                    const progressPercentage = task.completed ? 100 : Math.min((currentStrikes / maxStrikes) * 100, 100);
                    const progressStep = task.completed ? maxStrikes : Math.min(currentStrikes + 1, maxStrikes);
                    
                    console.log(`Rendering task ${task.title}: struck_today=${task.struck_today}, completed=${task.completed}, strike_count=${task.strike_count}`);
                    
                    return `
                        <div class="task-card ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${(task.struck_today && task.strike_count > 1) ? 'restrike' : ''}" data-task-id="${task.id}">
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
                            
                            <div class="task-meta-bottom-right">
                                ${task.due_date ? `<span class="task-due-pill${isDueToday(task.due_date) ? ' task-due-today' : ''}">${sanitizeHTML(formatDueDateLabel(task.due_date))}</span>` : ''}
                                <span class="task-duration-badge">${task.estimated_duration || task.duration || 60} min</span>
                            </div>
                        </div>
                    `;
                }).join('')}
            </div>
        `;
        Utils.Logger.log('Generated grid HTML');
        tasksList.innerHTML = gridHTML;
    } else {
        const listHTML = sortedTasks.map(task => {
            const hasDueDate = !!task.due_date;
            const dueLabel = hasDueDate ? formatDueDateLabel(task.due_date) : '';
            const dueTodayClass = hasDueDate && isDueToday(task.due_date) ? ' task-due-today' : '';
            const hasDescription = !!(task.description && task.description.trim());

            return `
        <div class="task-item ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${(task.struck_today && task.strike_count > 1) ? 'restrike' : ''}" data-task-id="${task.id}">
            <div class="task-project-tag">
                ${task.project ? `<span class="project-tag">${sanitizeHTML(task.project)}</span>` : '<span class="project-tag project-tag--no-project no-project">No Project</span>'}
            </div>
            <div class="task-content">
                <h3 class="task-title ${task.struck_today ? 'struck-today' : ''}">
                    ${sanitizeHTML(task.title)}
                    ${hasDescription ? `<button class=\"task-title-more\" onclick=\"openTaskDetailsModal('${task.id}')\" title=\"View details\"><i class=\"fas fa-chevron-right\"></i></button>` : ''}
                </h3>
                ${task.strike_report ? `<p class="strike-report"><em>Last strike: ${sanitizeHTML(task.strike_report)}</em></p>` : ''}
            </div>
            <div class="task-actions">
                ${hasDueDate ? `
                    <span class="task-due-pill${dueTodayClass}">${sanitizeHTML(dueLabel)}</span>
                ` : ''}
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
    `;
        }).join('');
        tasksList.innerHTML = listHTML;
    }
}

// Public entry: schedule render work into the next animation frame
// Modal showing full task details (title, project, due, full description)
function openTaskDetailsModal(taskId) {
    try {
        const tasks = (typeof AppState !== 'undefined' && AppState.getTasks) ? (AppState.getTasks() || []) : [];
        const task = tasks.find(t => String(t.id) === String(taskId));
        if (!task) {
            if (typeof Utils !== 'undefined' && Utils.safeShowNotification) {
                Utils.safeShowNotification('Could not load task details', 'error');
            }
            return;
        }

        let modal = document.getElementById('task-details-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'task-details-modal';
            modal.className = 'modal task-details-modal';
            document.body.appendChild(modal);
        }

        const description = (task.description || '').trim();
        const project = (task.project || '').trim() || 'No Project';
        const hasDueDate = !!task.due_date;
        const dueLabel = hasDueDate ? formatDueDateLabel(task.due_date) : 'No due date';

        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>${sanitizeHTML(task.title || 'Task details')}</h2>
                    <span class="close" onclick="closeTaskDetailsModal()">&times;</span>
                </div>
                <div class="task-details-body">
                    <div class="task-details-meta">
                        <span class="task-details-project">${sanitizeHTML(project)}</span>
                        <span class="task-details-due">${sanitizeHTML(dueLabel)}</span>
                    </div>
                    <div class="task-details-description">
                        ${description ? sanitizeHTML(description) : '<em>No description</em>'}
                    </div>
                </div>
            </div>
        `;

        modal.classList.add('active');
        modal.style.display = 'flex';
    } catch (e) {
        console.error('Failed to open task details modal', e);
    }
}

function closeTaskDetailsModal() {
    const modal = document.getElementById('task-details-modal');
    if (!modal) return;
    modal.classList.remove('active');
    modal.style.display = 'none';
}

function renderTasks(filter = AppState.get('currentFilter'), projectFilterArg) {
    if (_renderTasksRafId !== null) {
        if (typeof cancelAnimationFrame === 'function') {
            cancelAnimationFrame(_renderTasksRafId);
        } else {
            clearTimeout(_renderTasksRafId);
        }
        _renderTasksRafId = null;
    }
    const requestedFilter = filter;
    const requestedProjectFilter = projectFilterArg;
    _renderTasksRafId = _renderTasksSchedule(() => {
        _renderTasksRafId = null;
        _renderTasksNow(requestedFilter, requestedProjectFilter);
    });
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
    // Delegate to Tasks module if available to ensure AppState stays in sync
    if (window.Tasks && typeof window.Tasks.setActiveFilter === 'function') {
        return window.Tasks.setActiveFilter(filter);
    }
    // Fallback: keep both global and AppState in sync and update UI
    currentFilter = filter;
    if (window.AppState && typeof window.AppState.set === 'function') {
        window.AppState.set('currentFilter', filter);
    }
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.remove('active');
    });
    const activeTab = document.querySelector(`[data-filter="${filter}"]`);
    if (activeTab) activeTab.classList.add('active');
}

function filterTasks(filter) {
    // Ensure AppState reflects the requested filter before rendering
    if (window.AppState && typeof window.AppState.set === 'function') {
        window.AppState.set('currentFilter', filter);
    }
    renderTasks(filter);
}

// Dashboard Stats
function updateDashboardStats() {
    const tasks = AppState.getTasks();
    
    // Calculate completed today
    const completedToday = tasks.filter(task => {
        if (!task.completed || !task.completed_at) return false;
        const completedDate = new Date(task.completed_at);
        const today = new Date();
        return completedDate.toDateString() === today.toDateString();
    }).length;

    // Calculate expired tasks (tasks with due dates that have passed and are not completed)
    const expiredTasks = tasks.filter(task => {
        if (task.completed) return false;
        if (!task.due_date) return false;
        const dueDate = new Date(task.due_date);
        const today = new Date();
        today.setHours(23, 59, 59, 999); // End of today
        return dueDate < today;
    }).length;
    
    // Calculate streak (consecutive days with completed tasks)
    const streakDays = calculateStreak();
    
    // Calculate productivity score (completion rate)
    const productivityScore = calculateProductivityScore();

    // Calculate striked today
    const strikedToday = tasks.filter(task => task.struck_today && !task.completed).length;

    // Update DOM elements
    const completedTodayEl = document.getElementById('completed-today');
    const expiredTasksEl = document.getElementById('expired-tasks');
    const streakDaysEl = document.getElementById('streak-days');
    const productivityScoreEl = document.getElementById('productivity-score');
    const strikedTodayEl = document.getElementById('striked-today');
    
    if (completedTodayEl) completedTodayEl.textContent = completedToday;
    if (expiredTasksEl) expiredTasksEl.textContent = expiredTasks;
    if (streakDaysEl) streakDaysEl.textContent = streakDays;
    if (productivityScoreEl) productivityScoreEl.textContent = productivityScore + '%';
    if (strikedTodayEl) strikedTodayEl.textContent = strikedToday;
    
    // Update mini analytics in tasks header
    const headerStrikedToday = document.getElementById('header-striked-today');
    if (headerStrikedToday) {
        headerStrikedToday.textContent = strikedToday;
        console.log('Updated header striked today:', strikedToday);
    }
    
    // Also call updateTaskStats from tasks.js if available
    if (typeof Tasks !== 'undefined' && Tasks.updateTaskStats) {
        Tasks.updateTaskStats();
    }
}

function calculateStreak() {
    const tasks = AppState.getTasks();
    const completedTasks = tasks.filter(task => task.completed && task.completed_at);
    
    if (completedTasks.length === 0) return 0;
    
    // Sort completed tasks by completion date (most recent first)
    completedTasks.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at));
    
    let streak = 0;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    // Check consecutive days starting from today
    for (let i = 0; i < completedTasks.length; i++) {
        const completedDate = new Date(completedTasks[i].completed_at);
        completedDate.setHours(0, 0, 0, 0);
        
        const expectedDate = new Date(today);
        expectedDate.setDate(today.getDate() - i);
        
        if (completedDate.getTime() === expectedDate.getTime()) {
            streak++;
        } else {
            break;
        }
    }
    
    return streak;
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
    openScheduleModal,
    closeTaskModal,
    closeQuickAddModal,
    closeScheduleModal
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
        
        // Use backend autostart flag
        document.getElementById('autostart-toggle').checked = !!(settings.autostart_enabled);
        document.getElementById('autosave-interval').value = settings.autosave_interval || 30;
        document.getElementById('theme-selector').value = settings.theme || 'light';
        document.getElementById('finish-selector').value = settings.finish || 'glossy';
        document.getElementById('intensity-selector').value = settings.intensity || '5';
        document.getElementById('dpi-selector').value = settings.dpi_scale || 100;
        // Navbar planner style (stored locally)
        try {
            const navStyle = localStorage.getItem('navbar_planner_style') || 'modern';
            const sel = document.getElementById('navbar-planner-style');
            if (sel) sel.value = navStyle;
            if (window.NavbarScheduleCard && typeof window.NavbarScheduleCard.applyStyle === 'function') {
                window.NavbarScheduleCard.applyStyle(navStyle);
            }
        } catch(e) {}
        
        // Update version number text if present
        const verEl = document.querySelector('.version-number');
        if (verEl && window.APP_CONFIG && window.APP_CONFIG.version) {
            verEl.textContent = 'v' + window.APP_CONFIG.version;
        }
        
        // Try to reflect real autostart status from backend if available
        try {
            const autoResp = await fetch('/api/settings/autostart');
            if (autoResp.ok) {
                const autoData = await autoResp.json();
                if (typeof autoData.enabled === 'boolean') {
                    const el = document.getElementById('autostart-toggle');
                    if (el) el.checked = autoData.enabled;
                }
            }
        } catch (e) {
            // ignore
        }
        
        applyThemeAndDPI();
        
        // Hide loading screen after settings are applied
        hideLoadingScreen();

        // After settings + theme are ready, show one-time "What's New" modal if needed
        try {
            maybeShowWhatsNewModal();
        } catch (e) {
            console.error('Error showing What\'s New modal:', e);
        }
    } catch (error) {
        console.error('Error loading settings:', error);
        // Hide loading screen even if there's an error
        hideLoadingScreen();
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
    
    // Update CSS custom properties based on theme
    updateThemeCSSVariables(theme, intensity);
}

function updateThemeCSSVariables(theme, intensity) {
    const root = document.documentElement;
    const body = document.body;
    
    // Define theme color mappings
    const themeColors = {
        'light': {
            'primary-gradient': 'linear-gradient(135deg, #FF8C42, #FFB366)',
            'secondary-gradient': 'linear-gradient(135deg, #FFF5E6 0%, #FFE0B3 100%)',
            'background-color': '#FFF5E6',
            'surface-color': 'rgba(255, 255, 255, 0.95)',
            'text-color': '#5C2D00',
            'text-secondary': '#8B4513',
            'border-color': 'rgba(255, 140, 66, 0.3)',
            'shadow-color': 'rgba(255, 140, 66, 0.1)',
            'accent-color': '#FF8C42'
        },
        'dark': {
            'primary-gradient': 'linear-gradient(135deg, #4A90E2, #7BB3F0)',
            'secondary-gradient': 'linear-gradient(135deg, #1A1A2E 0%, #16213E 100%)',
            'background-color': '#1A1A2E',
            'surface-color': 'rgba(26, 26, 46, 0.95)',
            'text-color': '#E0E0E0',
            'text-secondary': '#B0B0B0',
            'border-color': 'rgba(74, 144, 226, 0.3)',
            'shadow-color': 'rgba(74, 144, 226, 0.1)',
            'accent-color': '#4A90E2'
        },
        'orange': {
            'primary-gradient': 'linear-gradient(135deg, #FF8C42, #FFB366)',
            'secondary-gradient': 'linear-gradient(135deg, #FFF5E6 0%, #FFE0B3 100%)',
            'background-color': '#FFF5E6',
            'surface-color': 'rgba(255, 255, 255, 0.95)',
            'text-color': '#5C2D00',
            'text-secondary': '#8B4513',
            'border-color': 'rgba(255, 140, 66, 0.3)',
            'shadow-color': 'rgba(255, 140, 66, 0.1)',
            'accent-color': '#FF8C42'
        },
        'self-esteem': {
            'primary-gradient': 'linear-gradient(135deg, #4ECDC4, #44A08D)',
            'secondary-gradient': 'linear-gradient(135deg, #E8F8F5 0%, #D1F2EB 100%)',
            'background-color': '#E8F8F5',
            'surface-color': 'rgba(255, 255, 255, 0.95)',
            'text-color': '#1B4D3E',
            'text-secondary': '#2E7D5F',
            'border-color': 'rgba(78, 205, 196, 0.3)',
            'shadow-color': 'rgba(78, 205, 196, 0.1)',
            'accent-color': '#4ECDC4'
        },
        'anxiety': {
            'primary-gradient': 'linear-gradient(135deg, #74B9FF, #0984E3)',
            'secondary-gradient': 'linear-gradient(135deg, #E3F2FD 0%, #BBDEFB 100%)',
            'background-color': '#E3F2FD',
            'surface-color': 'rgba(255, 255, 255, 0.95)',
            'text-color': '#0D47A1',
            'text-secondary': '#1565C0',
            'border-color': 'rgba(116, 185, 255, 0.3)',
            'shadow-color': 'rgba(116, 185, 255, 0.1)',
            'accent-color': '#74B9FF'
        }
    };
    
    // Apply intensity variations for orange theme
    if (theme === 'orange' && intensity !== '5') {
        const intensityMap = {
            '1': 'linear-gradient(135deg, #E6B8A0, #F0C4A0)',
            '2': 'linear-gradient(135deg, #F0A070, #F5B080)',
            '3': 'linear-gradient(135deg, #F59E42, #F7A855)',
            '4': 'linear-gradient(135deg, #FF8C42, #FF9A55)',
            '6': 'linear-gradient(135deg, #FF7A2E, #FF8C42)',
            '7': 'linear-gradient(135deg, #FF6B1A, #FF7A2E)',
            '8': 'linear-gradient(135deg, #FF5C06, #FF6B1A)',
            '9': 'linear-gradient(135deg, #FF4D00, #FF5C06)',
            '10': 'linear-gradient(135deg, #FF3D00, #FF4D00)'
        };
        if (intensityMap[intensity]) {
            themeColors.orange['primary-gradient'] = intensityMap[intensity];
        }
    }
    
    // Apply intensity variations for dark theme
    if (theme === 'dark' && intensity !== '5') {
        const intensityMap = {
            '1': 'linear-gradient(135deg, #6B9BC7, #8BB3D7)',
            '2': 'linear-gradient(135deg, #5A8BC2, #7BA3D2)',
            '3': 'linear-gradient(135deg, #4A90E2, #6BA0E7)',
            '4': 'linear-gradient(135deg, #3A80D2, #5B90D7)',
            '6': 'linear-gradient(135deg, #2A70C2, #4B80C7)',
            '7': 'linear-gradient(135deg, #1A60B2, #3B70B7)',
            '8': 'linear-gradient(135deg, #0A50A2, #2B60A7)',
            '9': 'linear-gradient(135deg, #004092, #1B5097)',
            '10': 'linear-gradient(135deg, #003082, #0B4087)'
        };
        if (intensityMap[intensity]) {
            themeColors.dark['primary-gradient'] = intensityMap[intensity];
        }
    }
    
    // Apply intensity variations for self-esteem theme
    if (theme === 'self-esteem' && intensity !== '5') {
        const intensityMap = {
            '1': 'linear-gradient(135deg, #7ED4C7, #8ED9CC)',
            '2': 'linear-gradient(135deg, #6EC9BC, #7ECEC1)',
            '3': 'linear-gradient(135deg, #5EBEB1, #6EC3B6)',
            '4': 'linear-gradient(135deg, #4ECDC4, #5ED2C9)',
            '6': 'linear-gradient(135deg, #3EBDC4, #4EC2C9)',
            '7': 'linear-gradient(135deg, #2EADC4, #3EB2C9)',
            '8': 'linear-gradient(135deg, #1E9DC4, #2EA2C9)',
            '9': 'linear-gradient(135deg, #0E8DC4, #1E92C9)',
            '10': 'linear-gradient(135deg, #007DC4, #0E82C9)'
        };
        if (intensityMap[intensity]) {
            themeColors['self-esteem']['primary-gradient'] = intensityMap[intensity];
        }
    }
    
    // Apply intensity variations for anxiety theme
    if (theme === 'anxiety' && intensity !== '5') {
        const intensityMap = {
            '1': 'linear-gradient(135deg, #8BC7FF, #9BCDFF)',
            '2': 'linear-gradient(135deg, #7BB7FF, #8BC7FF)',
            '3': 'linear-gradient(135deg, #6BA7FF, #7BB7FF)',
            '4': 'linear-gradient(135deg, #5B97FF, #6BA7FF)',
            '6': 'linear-gradient(135deg, #4B87FF, #5B97FF)',
            '7': 'linear-gradient(135deg, #3B77FF, #4B87FF)',
            '8': 'linear-gradient(135deg, #2B67FF, #3B77FF)',
            '9': 'linear-gradient(135deg, #1B57FF, #2B67FF)',
            '10': 'linear-gradient(135deg, #0B47FF, #1B57FF)'
        };
        if (intensityMap[intensity]) {
            themeColors.anxiety['primary-gradient'] = intensityMap[intensity];
        }
    }
    
        // Apply the theme colors to CSS custom properties
        const colors = themeColors[theme] || themeColors['light'];
        Object.entries(colors).forEach(([property, value]) => {
            root.style.setProperty(`--${property}`, value);
        });
        
        // Apply additional CSS custom properties that are used in the CSS
        const settings = AppState.get('currentSettings') || {};
        const dpiScale = settings.dpi_scale || 100;
        const additionalProperties = {
            'surface-finish-gradient': colors['secondary-gradient'],
            'box-shadow-primary': `0 ${4 * (dpiScale / 100)}px ${12 * (dpiScale / 100)}px ${colors['shadow-color']}`,
            'border-finish': `1px solid ${colors['border-color']}`,
            'backdrop-filter': 'blur(10px)',
            'text-primary': colors['text-color'],
            'text-secondary': colors['text-secondary'],
            'accent-gradient': colors['primary-gradient']
        };
        
        // Set CSS custom properties on both root and body for maximum compatibility
        Object.entries(additionalProperties).forEach(([property, value]) => {
            root.style.setProperty(`--${property}`, value);
            body.style.setProperty(`--${property}`, value);
        });
}

async function updateTheme() {
    const theme = document.getElementById('theme-selector').value;
    
    try {
        console.log('Updating theme to:', theme);
        const response = await fetch('/api/settings', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ theme: theme })
        });

        console.log('Theme update response:', response.status, response.statusText);
        
        if (response.ok) {
            const settings = AppState.get('currentSettings') || {};
            settings.theme = theme;
            AppState.set('currentSettings', settings);
            applyThemeAndDPI();
            showNotification('Theme updated successfully!', 'success');
        } else {
            const errorText = await response.text();
            console.error('Theme update failed:', response.status, errorText);
            throw new Error(`Failed to update theme: ${response.status} ${errorText}`);
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
        showNotification('Error updating intensity', 'error');
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
    const modal = document.getElementById('strike-modal');
    const reportEl = document.getElementById('strike-report');
    if (reportEl) reportEl.value = '';
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex'; // ensure visible even if CSS expects inline style
    }
    if (reportEl) reportEl.focus();
    addLog('info', `Opening strike modal for task ${taskId}`);
}

function closeStrikeModal() {
    const modal = document.getElementById('strike-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    const reportEl = document.getElementById('strike-report');
    if (reportEl) reportEl.value = '';
    currentStrikeTaskId = null;
}

async function strikeTaskToday() {
    const report = document.getElementById('strike-report').value.trim();
    
    if (!currentStrikeTaskId) {
        showNotification('No task selected', 'error');
        return;
    }
    
    // Check if task can still be struck today (guard against missing task state)
    const tasks = AppState.get('tasks') || [];
    const task = tasks.find(t => t.id === currentStrikeTaskId);
    if (task && !canStrikeTask(task)) {
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
            const updatedTask = await response.json().catch(() => null);
            closeStrikeModal();
            // Optimistically update AppState immediately
            try {
                if (updatedTask && window.AppState && AppState.updateTask) {
                    await AppState.updateTask(currentStrikeTaskId, updatedTask).catch(async () => {
                        if (AppState.addTask) {
                            await AppState.addTask(updatedTask);
                        }
                    });
                }
            } catch (e) { /* noop */ }
            // Full reload as safety
            await loadTasks();
            updateDashboardStats();
            try {
                if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.refresh === 'function') {
                    window.DailyPlannerV2.refresh();
                }
            } catch (e) { /* noop */ }
            // If currently on tasks page, re-render immediately
            try {
                if (AppState.get && AppState.get('currentPage') === 'tasks') {
                    renderTasks();
                }
            } catch (e) { /* noop */ }
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
            const updatedTask = await response.json().catch(() => null);
            closeStrikeModal();
            try {
                if (updatedTask && window.AppState && AppState.updateTask) {
                    await AppState.updateTask(currentStrikeTaskId, updatedTask).catch(async () => {
                        if (AppState.addTask) {
                            await AppState.addTask(updatedTask);
                        }
                    });
                }
            } catch (e) { /* noop */ }
            await loadTasks();
            updateDashboardStats();
            try {
                if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.refresh === 'function') {
                    window.DailyPlannerV2.refresh();
                }
            } catch (e) { /* noop */ }
            try {
                if (AppState.get && AppState.get('currentPage') === 'tasks') {
                    renderTasks();
                }
            } catch (e) { /* noop */ }
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
            // After undoing a strike, a task may move from expired/completed
            // back to active; refresh project filter options.
            try {
                if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
                    Tasks.updateProjectFilterOptions();
                }
            } catch (e) { /* no-op */ }
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
                date: new Date().toISOString().split('T')[0]
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
    // Support a few optional behaviors:
    // - options.persistent: if true, do not auto-dismiss; user must click the X
    // - options.onClick: optional callback invoked when the notification body is clicked
    const isPersistent = options && options.persistent === true;
    const onClick = options && typeof options.onClick === 'function' ? options.onClick : null;

    // Check if this is an authentication-related error
    const isAuthError = type === 'error' && (
        message.toLowerCase().includes('login') || 
        message.toLowerCase().includes('authentication') ||
        message.toLowerCase().includes('access') ||
        message.toLowerCase().includes('unauthorized')
    );
    
    // Ensure a single bottom-right notification container exists
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            right: 20px;
            bottom: 20px;
            z-index: 4000;
            display: flex;
            flex-direction: column;
            align-items: flex-end;
            gap: 10px;
        `;
        document.body.appendChild(container);
    }

    // Allow multiple notifications; they will stack bottom-up in this container
    // (no explicit limit here, but short lifetimes keep the list small)

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    
    // Make auth error and custom-click notifications clickable
    if (isAuthError || onClick) {
        notification.style.cursor = 'pointer';
    }
    if (isAuthError) {
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
    
    // Attach custom click handler if provided (excluding clicks on the close button)
    if (onClick) {
        notification.addEventListener('click', (evt) => {
            const target = evt.target;
            if (target && target.closest && target.closest('.notification-close')) {
                return; // close button uses its own handler
            }
            try {
                onClick();
            } catch (e) {
                console.error('Notification onClick handler failed', e);
            }
        });
    }
    
    // Add styles (container controls bottom-right positioning)
    notification.style.cssText = `
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
    // Authentication disabled - no special handling needed
    
    container.appendChild(notification);
    
    // Auto-open login dialog for auth errors
    if (isAuthError && options.autoOpenLogin !== false) {
        console.log('Auto-opening login dialog for auth error');
        setTimeout(() => {
            // Use PIN authentication system
            if (typeof window.showAuthModal === 'function') {
                window.showAuthModal('login');
            } else if (typeof window.PINAuthInstance !== 'undefined') {
                window.PINAuthInstance.init();
            }
        }, 1000); // Small delay to let user see the notification first
    }
    
    // Auto-dismiss non-persistent notifications after 2 seconds (short snack-style).
    if (!isPersistent) {
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.animation = 'slideOutRight 0.3s ease-in-out';
                setTimeout(() => {
                    if (notification.parentNode) {
                        notification.parentNode.removeChild(notification);
                    }
                }, 300);
            }
        }, 2000);
    }
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
        
        // Try to call the backend shutdown endpoint
        fetch('/api/shutdown', {
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
let updatePollInterval = null;
let isUpdateDownloading = false;
let lastUpdateStatus = null;

// Unified update check handler for the Settings "Check for Updates" button.
// This now delegates to the GitHub-based check so that any newer version
// published on GitHub will surface via the GitHub update modal.
async function checkForUpdates() {
    return checkGitHubUpdate();
}

async function checkGitHubUpdate() {
    try {
        const branchElement = document.getElementById('github-branch');
        const branch = branchElement ? branchElement.value : 'main';
        showNotification('Checking GitHub for updates...', 'info');
        
        const response = await fetch('/api/github/check-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ branch: branch })
        });
        
        const result = await response.json();
        
        if (result.update_available) {
            showGitHubUpdateModal(result);
            showNotification('GitHub update available!', 'success');
        } else {
            showNotification(`You are up to date! (${result.current_version})`, 'success');
        }
    } catch (error) {
        console.error('Error checking GitHub update:', error);
        showNotification('Error checking GitHub for updates', 'error');
    }
}

async function downloadGitHubUpdate() {
    try {
        const branchElement = document.getElementById('github-branch');
        const branch = branchElement ? branchElement.value : 'main';
        showNotification('Downloading update from GitHub...', 'info');

        // Show progress UI in the GitHub update modal
        const progressDiv = document.getElementById('github-update-progress');
        const progressFill = document.getElementById('github-progress-fill');
        const progressText = document.getElementById('github-progress-text');
        if (progressDiv && progressFill && progressText) {
            progressDiv.style.display = 'block';
            progressFill.style.width = '0%';
            progressText.textContent = 'Starting download...';
        }

        // Simple front-end progress simulation while the download request runs.
        // This does not reflect exact bytes, but gives visual feedback.
        let fakePct = 0;
        let progressTimer = null;
        if (progressDiv && progressFill && progressText) {
            progressTimer = setInterval(() => {
                if (fakePct < 95) {
                    fakePct += 3;
                    progressFill.style.width = Math.min(fakePct, 95) + '%';
                    progressText.textContent = 'Downloading update...';
                }
            }, 500);
        }
        
        const response = await fetch('/api/github/download-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ branch: branch })
        });
        
        const result = await response.json();

        if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
        }
        
        if (result.success) {
            const path = result.installer_path || 'the downloaded installer file';
            if (progressDiv && progressFill && progressText) {
                progressFill.style.width = '100%';
                progressText.textContent = 'Download complete.';
            }
            // Short success snack about the update itself
            showNotification('Update installer downloaded. Please close Shakshuka and run the installer to finish updating.', 'success');

            // Persistent, clickable toast that shows where the file went and
            // lets the user open the folder directly.
            const friendlyPath = path;
            const safeMessage = `Download finished to "${friendlyPath}" (click to open folder)`;
            showNotification(safeMessage, 'info', {
                persistent: true,
                onClick: () => {
                    try {
                        const payload = encodeURIComponent(friendlyPath);
                        window.location.href = `shakshuka-open-folder://${payload}`;
                    } catch (e) {
                        console.error('Failed to trigger folder open for installer path', e);
                    }
                }
            });

            // Close any open modals
            try { closeUpdateModal(); } catch (_) {}
            try { closeGitHubUpdateModal(); } catch (_) {}
        } else {
            if (progressDiv && progressText) {
                progressText.textContent = 'Download failed.';
            }
            showNotification(`Update failed: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error downloading GitHub update:', error);
        showNotification('Error downloading update from GitHub', 'error');
    }
}

function showGitHubUpdateModal(updateInfo) {
    const modal = document.getElementById('github-update-modal');
    if (!modal) {
        // Create modal if it doesn't exist
        createGitHubUpdateModal();
    }
    
    const modalElement = document.getElementById('github-update-modal');
    const updateInfoDiv = document.getElementById('github-update-info');
    
    if (updateInfoDiv) {
        updateInfoDiv.innerHTML = `
            <div class="update-info">
                <h3>GitHub Update Available</h3>
                <div class="version-info">
                    <p><strong>Current Version:</strong> ${updateInfo.current_version}</p>
                    <p><strong>Latest Version:</strong> ${updateInfo.latest_version}</p>
                    <p><strong>Release:</strong> ${updateInfo.release_info.tag_name}</p>
                    <p><strong>Published:</strong> ${new Date(updateInfo.release_info.published_at).toLocaleDateString()}</p>
                </div>
                <div class="release-notes">
                    <h4>Release Notes:</h4>
                    <div class="release-body">${updateInfo.release_info.body || 'No release notes available.'}</div>
                </div>
            </div>
        `;
    }
    
    modalElement.style.display = 'flex';
    modalElement.classList.add('active');
}

function closeGitHubUpdateModal() {
    const modal = document.getElementById('github-update-modal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
}

function createGitHubUpdateModal() {
    const modalHTML = `
        <div id=\"github-update-modal\" class=\"modal\">
            <div class=\"modal-content\">
                <div class=\"modal-header\">
                    <h2>GitHub Update</h2>
                    <button class=\"modal-close\" id=\"close-github-update-modal\">&times;</button>
                </div>
                <div id=\"github-update-info\" class=\"modal-body\">
                    <!-- Update info will be populated here -->
                    <div class=\"update-progress\" id=\"github-update-progress\" style=\"display:none; margin-top: 1rem;\">
                        <div class=\"progress-bar\">
                            <div class=\"progress-fill\" id=\"github-progress-fill\"></div>
                        </div>
                        <p class=\"progress-text\" id=\"github-progress-text\"></p>
                    </div>
                </div>
                <div class=\"modal-footer\">
                    <button class=\"btn-secondary\" id=\"cancel-github-update\">Cancel</button>
                    <button class=\"btn-primary\" id=\"download-github-update\">Download & Install</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
    // Bind events for dynamically created elements
    const closeBtn = document.getElementById('close-github-update-modal');
    if (closeBtn) closeBtn.addEventListener('click', closeGitHubUpdateModal);
    const cancelBtn = document.getElementById('cancel-github-update');
    if (cancelBtn) cancelBtn.addEventListener('click', closeGitHubUpdateModal);
    const dlBtn = document.getElementById('download-github-update');
    if (dlBtn) dlBtn.addEventListener('click', downloadGitHubUpdate);
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
    
    // Reset progress UI
    const progressDiv = document.getElementById('update-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    if (progressDiv) progressDiv.style.display = 'none';
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = '';
    isUpdateDownloading = false;
    
    modal.classList.add('active');
}

function closeUpdateModal() {
    document.getElementById('update-modal').classList.remove('active');
    currentUpdateInfo = null;
}

async function downloadAndInstallUpdate() {
    if (!currentUpdateInfo) return;
    const progressDiv = document.getElementById('update-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    // UI state
    progressDiv.style.display = 'block';
    progressText.textContent = 'Starting download...';
    isUpdateDownloading = true;
    
    // Start polling progress
    if (updatePollInterval) clearInterval(updatePollInterval);
    updatePollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/updates/progress');
            const status = await res.json();
            lastUpdateStatus = status;
            const st = (status.status || '').toLowerCase();
            if (st === 'downloading') {
                const pct = Math.max(0, Math.min(100, status.progress || 0));
                progressFill.style.width = pct + '%';
                const downloadedMB = ((status.downloaded || 0) / (1024*1024)).toFixed(1);
                const totalMB = status.total ? ((status.total)/(1024*1024)).toFixed(1) : '...';
                progressText.textContent = `Downloading update... ${pct}% (${downloadedMB} / ${totalMB} MB)`;
            } else if (st === 'ready') {
                progressFill.style.width = '100%';
                progressText.textContent = 'Installing update...';
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                // Trigger install using the reported file name
                const fileName = status.update_file || `update_${currentUpdateInfo.version}.zip`;
                const installResponse = await fetch('/api/updates/install', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ update_file: fileName, backup_before_update: true })
                });
                if (!installResponse.ok) throw new Error('Failed to install update');
                showNotification('Update installed successfully! Please restart the application.', 'success');
                isUpdateDownloading = false;
                closeUpdateModal();
            } else if (st === 'failed') {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                isUpdateDownloading = false;
                showNotification('Update failed: ' + (status.error || 'Unknown error'), 'error');
            } else if (st === 'canceled') {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                isUpdateDownloading = false;
                progressDiv.style.display = 'none';
                progressFill.style.width = '0%';
                progressText.textContent = '';
                showNotification('Update download canceled', 'info');
            }
        } catch (e) {
            console.error('Progress poll error:', e);
        }
    }, 800);
    
    // Kick off background download
    try {
        const response = await fetch('/api/updates/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentUpdateInfo)
        });
        if (!response.ok && response.status !== 202) {
            throw new Error('Failed to start download');
        }
    } catch (e) {
        clearInterval(updatePollInterval);
        updatePollInterval = null;
        isUpdateDownloading = false;
        showNotification('Error starting update download', 'error');
    }
}

async function cancelOrCloseUpdateModal() {
    const progressDiv = document.getElementById('update-progress');
    const isVisible = progressDiv && progressDiv.style.display !== 'none';
    if (isVisible && isUpdateDownloading) {
        try {
            await fetch('/api/updates/cancel', { method: 'POST' });
        } catch (e) { /* ignore */ }
        if (updatePollInterval) { clearInterval(updatePollInterval); updatePollInterval = null; }
        isUpdateDownloading = false;
        progressDiv.style.display = 'none';
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = '';
        showNotification('Canceled update download', 'info');
        closeUpdateModal();
    } else {
        closeUpdateModal();
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
        
        // Safely set values with null checks
        const autoCheckEl = document.getElementById('auto-update-check');
        const autoInstallEl = document.getElementById('auto-update-install');
        const backupEl = document.getElementById('backup-before-update');
        const channelEl = document.getElementById('update-channel');
        const intervalEl = document.getElementById('check-interval');
        
        if (autoCheckEl) autoCheckEl.checked = config.auto_check_enabled || false;
        if (autoInstallEl) autoInstallEl.checked = config.auto_install_enabled || false;
        if (backupEl) backupEl.checked = config.backup_before_update !== false;
        if (channelEl) channelEl.value = config.update_channel || 'stable';
        if (intervalEl) intervalEl.value = config.check_interval_hours || 24;
    } catch (error) {
        console.error('Error loading update settings:', error);
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

    const helpers = window.TaskHelpers;
    if (!helpers) {
        console.warn('TaskHelpers not available, returning tasks unfiltered');
        return tasks;
    }
    
    switch (filter) {
        case 'active':
            return tasks.filter(helpers.isActive);
        case 'completed':
            return tasks.filter(helpers.isDone);
        case 'expired':
            return tasks.filter(helpers.isExpired);
        default:
            return tasks;
    }
}

// Quick date helpers for due date buttons
function setQuickDate(kind) {
    const el = document.getElementById('task-due-date');
    if (!el) return;
    const today = new Date();
    let date = new Date(today);
    if (kind === 'today') {
        // date already today
    } else if (kind === 'tomorrow') {
        date.setDate(date.getDate() + 1);
    } else if (kind === 'thisweek') {
        const day = date.getDay(); // 0-6
        const diff = 6 - day; // go to Saturday as end of week
        date.setDate(date.getDate() + (diff > 0 ? diff : 0));
    }
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    el.value = `${yyyy}-${mm}-${dd}`;
}

// Helper: determine if a given date string is today (compares by date only)
function isDueToday(dueRaw) {
    if (!dueRaw) return false;
    try {
        const raw = String(dueRaw);
        const dateOnly = raw.split('T')[0];
        const today = new Date();
        const todayStr = today.toISOString().split('T')[0];
        return dateOnly === todayStr;
    } catch (e) {
        return false;
    }
}

// Human-friendly label for due dates used in task cards
function formatDueDateLabel(dueRaw) {
    if (!dueRaw) return '';
    try {
        const raw = String(dueRaw);
        const dateOnly = raw.split('T')[0];
        const dueDate = new Date(dateOnly + 'T00:00:00');
        const today = new Date();
        today.setHours(0, 0, 0, 0);

        const diffDays = Math.round((dueDate - today) / (1000 * 60 * 60 * 24));

        // Default (non-casual) formatting
        let settings = {};
        try {
            settings = (typeof AppState !== 'undefined' && AppState.get)
                ? (AppState.get('currentSettings') || {})
                : {};
        } catch (e) {
            settings = {};
        }

        const useCasual = !!settings.casual_dates;

        if (!useCasual) {
            // Non-casual mode: always show the raw YYYY-MM-DD date
            return dateOnly;
        }

        // Casual formatting
        if (diffDays === 0) return 'today';
        if (diffDays === 1) return 'tomorrow';
        if (diffDays === -1) return 'yesterday';
        if (diffDays < -1) return `${Math.abs(diffDays)} days ago`;

        // Weekend helpers (Saturday/Sunday)
        const todayDow = today.getDay(); // 0-6, Sunday=0
        const thisSaturday = new Date(today);
        thisSaturday.setDate(today.getDate() + ((6 - todayDow + 7) % 7));
        const thisSunday = new Date(thisSaturday);
        thisSunday.setDate(thisSaturday.getDate() + 1);

        const nextSaturday = new Date(thisSaturday);
        nextSaturday.setDate(thisSaturday.getDate() + 7);
        const nextSunday = new Date(nextSaturday);
        nextSunday.setDate(nextSaturday.getDate() + 1);

        const isSameDay = (d1, d2) => d1.getFullYear() === d2.getFullYear()
            && d1.getMonth() === d2.getMonth()
            && d1.getDate() === d2.getDate();

        if (isSameDay(dueDate, thisSaturday) || isSameDay(dueDate, thisSunday)) {
            return 'this weekend';
        }
        if (isSameDay(dueDate, nextSaturday) || isSameDay(dueDate, nextSunday)) {
            return 'next weekend';
        }

        if (diffDays > 1) {
            return `in ${diffDays} days`;
        }

        // For past dates or unexpected values, fall back to the raw date
        return dateOnly;
    } catch (e) {
        return String(dueRaw);
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

// Helper to apply "quick project from title" rule for NEW tasks.
// If enabled in settings and no project is specified, a title like
// "Work, finish report" becomes project="Work" and title="finish report".
function applyQuickProjectFromTitle(taskData) {
    try {
        const settings = (typeof AppState !== 'undefined' && AppState.get)
            ? (AppState.get('currentSettings') || {})
            : {};
        if (!settings.quick_project_from_title) {
            return taskData;
        }
    } catch (e) {
        return taskData;
    }

    // Only when project is empty or whitespace
    if (taskData.project && taskData.project.trim()) {
        return taskData;
    }

    const title = (taskData.title || '').trim();
    const commaIndex = title.indexOf(',');
    if (commaIndex <= 0) {
        return taskData;
    }

    const prefix = title.slice(0, commaIndex);
    const firstWord = prefix.trim().split(/\s+/)[0];
    if (!firstWord) {
        return taskData;
    }

    const rest = title.slice(commaIndex + 1).trim();
    return {
        ...taskData,
        title: rest,
        project: firstWord
    };
}


// Consolidated save function to avoid duplication
async function saveTaskCommon(taskData, modalCloseFn) {
    console.log('saveTaskCommon called with:', taskData);
    console.log('User ID in saveTaskCommon:', AppState.get('userId'));
    
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
        const editingTaskId = AppState.get('editingTaskId');
        if (editingTaskId) {
            await updateTask(editingTaskId, taskData);
        } else {
            // New task: optionally extract project from title if enabled
            taskData = applyQuickProjectFromTitle(taskData);
            await createTask(taskData);
        }
        
        console.log('Task saved successfully, closing modal...');
        modalCloseFn();
        console.log('Modal close function called');
        return true;
    } catch (error) {
        console.log('Error caught in saveTaskCommon:', error);
        console.log('Error message:', error.message);
        console.log('Error stack:', error.stack);
        Utils.Logger.error('Error saving task:', error);
        return false;
    }
}

// Duplicate saveTask function removed - using the first one

async function saveQuickTask() {
    // Prevent duplicate task creation
    if (window.taskCreationInProgress) {
        console.log('Task creation already in progress, skipping duplicate call');
        return;
    }
    
    window.taskCreationInProgress = true;
    
    try {
        console.log('saveQuickTask called');
        let taskData = {
            title: document.getElementById('quick-task-title').value.trim(),
            description: '',
            project: '',
            estimated_duration: 60
        };
        
        console.log('Quick task data (before quick-project rule):', taskData);
        console.log('User ID from AppState:', AppState.get('userId'));

        await saveTaskCommon(taskData, closeQuickAddModal);
    } finally {
        // Always reset the flag, even if an error occurs
        window.taskCreationInProgress = false;
    }
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

// Analytics dashboard updater
function updateDashboardStats() {
    const tasks = (AppState.get && AppState.get('tasks')) || [];
    const today = new Date();
    const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());

    const strikedToday = tasks.filter(t => t.struck_today).length;
    const completedForever = tasks.filter(t => t.struck_forever).length;
    const total = tasks.length;
    const overdue = tasks.filter(t => {
        if (!t.due_date) return false;
        const d = new Date(t.due_date);
        return d < startOfToday && !t.struck_forever;
    }).length;

    // productivity = completed forever / total
    const productivity = total > 0 ? Math.round((completedForever / total) * 100) : 0;

    // tasks added = total
    const settingsChanges = parseInt(localStorage.getItem('settings_changes_count') || '0', 10);

    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    setText('completed-today', strikedToday);
    setText('expired-tasks', overdue);
    setText('streak-days', localStorage.getItem('streak_days') || 0);
    setText('productivity-score', productivity + '%');
    setText('striked-today', strikedToday);

    // New widgets
    setText('tasks-added', total);
    setText('completed-forever', completedForever);
    setText('settings-changes', settingsChanges);
}

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

// ========================================
// GLOBAL API CALL HELPER WITH CREDENTIALS
// ========================================
// Helper function for authenticated API calls with credentials
// This replaces makeAuthenticatedRequest with better FormData handling
async function apiCall(url, options = {}) {
    const headers = {
        ...options.headers
    };
    
    // Only set Content-Type for non-FormData bodies
    if (!(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }
    
    return fetch(url, {
        ...options,
        credentials: 'include',
        headers
    });
}

// Make apiCall globally accessible
window.apiCall = apiCall;

// Navbar compact schedule card
(function(){
    function getDateKey(date){
        const y = date.getFullYear();
        const m = String(date.getMonth()+1).padStart(2,'0');
        const d = String(date.getDate()).padStart(2,'0');
        return `${y}-${m}-${d}`;
    }
    function toMinutes(h, m){ return (h*60)+m; }
    function formatTime(h, m){
        const hour = (h % 12) || 12;
        const min = String(m).padStart(2,'0');
        const ampm = h < 12 ? 'AM' : 'PM';
        return `${hour}:${min} ${ampm}`;
    }
    async function fetchScheduleFor(date){
        try {
            const resp = await apiCall('/api/planner-v2/schedule');
            const data = await resp.json();
            const key = getDateKey(date);
            const byHour = (data && data.scheduled_tasks && data.scheduled_tasks[key]) || {};
            const entries = [];
            Object.entries(byHour).forEach(([hourKey, arr])=>{
                const baseHour = parseInt(hourKey,10) || 0;
                (arr || []).forEach(t=>{
                    const h = (typeof t.scheduled_hour === 'number') ? t.scheduled_hour : baseHour;
                    const mm = (typeof t.scheduled_minute === 'number') ? t.scheduled_minute : (t.scheduled_minute ? parseInt(t.scheduled_minute,10) : 0);
                    const dur = parseInt(t.scheduled_duration || t.estimated_duration || 30,10);
                    entries.push({ id: t.id, title: t.title, startH: h, startM: mm, dur });
                });
            });
            // Dedup by id (prefer earliest start)
            const byId = new Map();
            for(const e of entries){
                if(!byId.has(e.id)) byId.set(e.id, e);
                else {
                    const ex = byId.get(e.id);
                    const exMin = toMinutes(ex.startH, ex.startM);
                    const curMin = toMinutes(e.startH, e.startM);
                    if (curMin < exMin) byId.set(e.id, e);
                }
            }
            return Array.from(byId.values()).sort((a,b)=> toMinutes(a.startH,a.startM) - toMinutes(b.startH,b.startM));
        } catch (e) {
            return [];
        }
    }
    async function updateCard(){
        const card = document.getElementById('nav-compact-schedule');
        if (!card) return;
        const now = new Date();
        const nowMin = toMinutes(now.getHours(), now.getMinutes());
        const list = await fetchScheduleFor(now);

        // If nothing scheduled today, show CTA to plan
        if (Array.isArray(list) && list.length === 0) {
            const curTitleEl = card.querySelector('#nav-current-title');
            const curTimeEl = card.querySelector('#nav-current-time');
            const nextTitleEl = card.querySelector('#nav-next-title');
            const nextTimeEl = card.querySelector('#nav-next-time');
            const curBadge = card.querySelector('#nav-current-badge');
            const nextBadge = card.querySelector('#nav-next-badge');
            if (curTitleEl) curTitleEl.textContent = 'Nothing scheduled';
            if (curTimeEl) {
                curTimeEl.innerHTML = '<a href=\"#\" id=\"nav-plan-now-link\">Plan now?</a>';
                const link = card.querySelector('#nav-plan-now-link');
                if (link) {
                    link.addEventListener('click', (e) => {
                        e.preventDefault();
                        try { navigateToPage('planner'); } catch(e) {
                            const btn = document.querySelector('.nav-item[data-page="planner"]');
                            if (btn) btn.click();
                        }
                        try { if (typeof window.ensurePlannerV2Init === 'function') { window.ensurePlannerV2Init(); } } catch(e) {}
                    }, { once: true });
                }
            }
            if (nextTitleEl) nextTitleEl.textContent = '—';
            if (nextTimeEl) nextTimeEl.textContent = '—';
            if (curBadge) curBadge.textContent = 'Now';
            if (nextBadge) nextBadge.textContent = 'Next';
            return;
        }

        let current = null, next = null;
        for(const t of list){
            const start = toMinutes(t.startH, t.startM);
            const end = start + t.dur;
            if (nowMin >= start && nowMin < end) { current = t; break; }
            if (nowMin < start) { next = t; break; }
        }
        if (!current){
            // ensure next if none yet
            for(const t of list){
                const start = toMinutes(t.startH, t.startM);
                if (nowMin < start) { next = t; break; }
            }
        } else {
            // next after current
            const after = list.filter(t=> toMinutes(t.startH,t.startM) >= (toMinutes(current.startH,current.startM)+current.dur));
            if (after.length) next = after[0];
        }
        const curTitleEl = card.querySelector('#nav-current-title');
        const curTimeEl = card.querySelector('#nav-current-time');
        const nextTitleEl = card.querySelector('#nav-next-title');
        const nextTimeEl = card.querySelector('#nav-next-time');
        const curBadge = card.querySelector('#nav-current-badge');
        const nextBadge = card.querySelector('#nav-next-badge');

        // Realtime CTA: if neither current nor next, offer to plan
        if (!current && !next) {
            if (curTitleEl) curTitleEl.textContent = 'Nothing scheduled';
            if (curTimeEl) {
                curTimeEl.innerHTML = '<a href=\"#\" id=\"nav-plan-now-link\">Plan now?</a>';
                const link = card.querySelector('#nav-plan-now-link');
                if (link) {
                    link.addEventListener('click', (e) => {
                        e.preventDefault();
                        try { navigateToPage('planner'); } catch(e) {
                            const btn = document.querySelector('.nav-item[data-page="planner"]');
                            if (btn) btn.click();
                        }
                        try { if (typeof window.ensurePlannerV2Init === 'function') { window.ensurePlannerV2Init(); } } catch(e) {}
                    }, { once: true });
                }
            }
            if (nextTitleEl) nextTitleEl.textContent = '—';
            if (nextTimeEl) nextTimeEl.textContent = '—';
            if (curBadge) curBadge.textContent = 'Now';
            if (nextBadge) nextBadge.textContent = 'Next';
            return;
        }

        if (current){
            curTitleEl.textContent = current.title || 'Untitled';
            const endTotal = current.startH*60+current.startM+current.dur;
            curTimeEl.textContent = `${formatTime(current.startH,current.startM)} - ${formatTime(Math.floor(endTotal/60), endTotal%60)}`;
        } else {
            curTitleEl.textContent = 'None';
            curTimeEl.textContent = '—';
        }
        if (next){
            nextTitleEl.textContent = next.title || 'Untitled';
            nextTimeEl.textContent = `${formatTime(next.startH,next.startM)}`;
        } else {
            nextTitleEl.textContent = 'None';
            nextTimeEl.textContent = '—';
        }
        if (curBadge) curBadge.textContent = 'Now';
        if (nextBadge) nextBadge.textContent = 'Next';

        // Slot-level CTA cases
        const makePlanLink = (el) => {
            if (!el) return;
            el.innerHTML = '<a href=\"#\" class=\"nav-plan-now-link\">Plan now?</a>';
            const link = el.querySelector('.nav-plan-now-link');
            if (link) {
                link.addEventListener('click', (e) => {
                    e.preventDefault();
                    try { navigateToPage('planner'); } catch(e) {
                        const btn = document.querySelector('.nav-item[data-page="planner"]');
                        if (btn) btn.click();
                    }
                    try { if (typeof window.ensurePlannerV2Init === 'function') { window.ensurePlannerV2Init(); } } catch(e) {}
                }, { once: true });
            }
        };
        if (current && !next) {
            // Offer to plan in the Next slot
            if (nextTitleEl) nextTitleEl.textContent = 'None';
            makePlanLink(nextTimeEl);
        }
        if (!current && next) {
            // Offer to plan in the Now slot
            if (curTitleEl) curTitleEl.textContent = 'None';
            makePlanLink(curTimeEl);
        }
    }
window.NavbarScheduleCard = {
        init(){
            if (this._timer) clearInterval(this._timer);
            this.applyStyle(this.getStyle());
            updateCard();
            this._timer = setInterval(updateCard, 60000);
        },
        update: updateCard,
        getStyle(){
            try { return localStorage.getItem('navbar_planner_style') || 'modern'; } catch(e){ return 'modern'; }
        },
        applyStyle(style){
            const card = document.getElementById('nav-compact-schedule');
            if (!card) return;
            card.classList.remove('clean','modern');
            card.classList.add(style === 'modern' ? 'modern' : 'clean');
        },
        setStyle(style){
            try { localStorage.setItem('navbar_planner_style', style); } catch(e) {}
            this.applyStyle(style);
            updateCard();
        }
    };
})();

