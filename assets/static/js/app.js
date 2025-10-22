// Main Shakshuka Application - Module Architecture

// Import all modules
// Note: These will be loaded in the HTML template in the correct order

// Loading screen management
function hideLoadingScreen() {
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');
    
    if (loadingScreen && appContainer) {
        // Add fade-out class
        loadingScreen.classList.add('fade-out');
        
        // Show app container
        appContainer.style.display = 'block';
        
        // Remove loading screen after fade animation
        setTimeout(() => {
            loadingScreen.style.display = 'none';
        }, 500);
    }
}

// Show loading screen initially
function showLoadingScreen() {
    const loadingScreen = document.getElementById('loading-screen');
    const appContainer = document.getElementById('app-container');
    
    if (loadingScreen && appContainer) {
        loadingScreen.style.display = 'flex';
        appContainer.style.display = 'none';
    }
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

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', async function() {
    console.log('Shakshuka application initializing...');
    
    // Show loading screen immediately
    showLoadingScreen();

    // Check authentication status and wait for it to complete
    await Auth.checkAuthStatus();

    // Setup event listeners only once
    if (!window.eventListenersSetup) {
    setupEventListeners();
        window.eventListenersSetup = true;
    }

    console.log('Shakshuka application initialized');
});

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

    // Reload data for new date if needed
    if (AppState.get('currentPage') === 'planner') {
        generateTimeSlots();
    }
}

// Settings functions
async function updateAutostart() {
    const enabled = document.getElementById('autostart-toggle').checked;
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/autostart', {
            method: 'POST',
            body: JSON.stringify({ enabled })
        });

        if (response.ok) {
            Utils.safeShowNotification('Autostart setting updated', 'success');
        } else {
            Utils.safeShowNotification('Failed to update autostart setting', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to update autostart:', error);
        Utils.safeShowNotification('Failed to update autostart setting', 'error');
    }
}

async function updateAutosaveInterval() {
    const interval = parseInt(document.getElementById('autosave-interval').value);
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/autosave', {
            method: 'POST',
            body: JSON.stringify({ interval })
        });

        if (response.ok) {
            Utils.safeShowNotification('Autosave interval updated', 'success');
        } else {
            Utils.safeShowNotification('Failed to update autosave interval', 'error');
        }
    } catch (error) {
        Utils.Logger.error('Failed to update autosave interval:', error);
        Utils.safeShowNotification('Failed to update autosave interval', 'error');
    }
}

async function updateDailyResetTime() {
    const time = document.getElementById('daily-reset-time').value;
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/reset-time', {
            method: 'POST',
            body: JSON.stringify({ time })
        });

        if (response.ok) {
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
    const channel = document.getElementById('update-channel').value;
    const autoUpdate = document.getElementById('auto-update-check').checked;
    const autoInstall = document.getElementById('auto-update-install').checked;
    const backupBeforeUpdate = document.getElementById('backup-before-update').checked;
    const githubAutoUpdate = document.getElementById('github-auto-update').checked;
    const githubBranch = document.getElementById('github-branch').value;
    const checkInterval = document.getElementById('check-interval').value;

    try {
        const response = await Utils.makeAuthenticatedRequest('/api/settings/updates', {
            method: 'POST',
            body: JSON.stringify({ 
                channel, 
                auto_update: autoUpdate,
                auto_install: autoInstall,
                backup_before_update: backupBeforeUpdate,
                github_auto_update: githubAutoUpdate,
                github_branch: githubBranch,
                check_interval: checkInterval
            })
        });

        if (response.ok) {
            Utils.safeShowNotification('Update settings updated', 'success');
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
    // loadSettings(); // Use the complete version at line 2712 instead
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
        Utils.Logger.error('Failed to load account settings:', error);
    }
}

// Theme and DPI Functions

// Setup daily reset
function setupDailyReset() {
    // Cancel existing timer
    const existingTimer = AppState.get('dailyResetTimer');
    if (existingTimer) {
        clearInterval(existingTimer);
    }

    // Setup new timer
    const settings = AppState.get('currentSettings');
    const resetTime = settings.daily_reset_time || '00:00';

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
function resetDailyStrikes() {
    // This function would reset all "struck today" tasks
    console.log('Resetting daily strikes');
    
    // Call the backend API to reset daily strikes
    fetch('/api/tasks/reset-daily-strikes', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            console.log('Daily strikes reset successfully');
            // Reload tasks to reflect the reset
            loadTasks();
            updateDashboardStats();
        } else {
            console.error('Failed to reset daily strikes:', data.error);
        }
    })
    .catch(error => {
        console.error('Error resetting daily strikes:', error);
    });
}

// Setup keyboard shortcuts
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', function(e) {
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
    // Parse the changelog markdown into version sections
    const sections = [];
    const lines = markdown.split('\n');
    let currentSection = null;
    
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // Check for version headers (## Version X.X.X)
        if (line.startsWith('## Version ')) {
            if (currentSection) {
                sections.push(currentSection);
            }
            currentSection = {
                version: line.replace('## Version ', '').split(' - ')[0],
                title: line.replace('## Version ', ''),
                content: [],
                date: null
            };
        }
        // Check for release date
        else if (line.startsWith('Release Date:') && currentSection) {
            currentSection.date = line.replace('Release Date:', '').trim();
        }
        // Add content to current section
        else if (currentSection && line) {
            currentSection.content.push(line);
        }
    }
    
    // Add the last section
    if (currentSection) {
        sections.push(currentSection);
    }
    
    // Sort by version (latest first) - simple version comparison
    sections.sort((a, b) => {
        const versionA = a.version.split('.').map(Number);
        const versionB = b.version.split('.').map(Number);
        
        for (let i = 0; i < Math.max(versionA.length, versionB.length); i++) {
            const numA = versionA[i] || 0;
            const numB = versionB[i] || 0;
            if (numA !== numB) {
                return numB - numA; // Descending order (latest first)
            }
        }
        return 0;
    });
    
    return sections;
}

function formatChangelogSections(sections) {
    let html = '<div class="changelog-sections">';
    
    sections.forEach((section, index) => {
        const isExpanded = index === 0; // Expand first (latest) section by default
        const sectionId = `changelog-section-${index}`;
        
        html += `
            <div class="changelog-section">
                <div class="changelog-section-header" onclick="toggleChangelogSection('${sectionId}')">
                    <div class="changelog-section-title">
                        <h3>${section.title}</h3>
                        ${section.date ? `<span class="changelog-date">${section.date}</span>` : ''}
                    </div>
                    <div class="changelog-section-toggle">
                        <i class="fas fa-chevron-${isExpanded ? 'up' : 'down'}"></i>
                    </div>
                </div>
                <div class="changelog-section-content ${isExpanded ? 'expanded' : ''}" id="${sectionId}">
                    <div class="changelog-section-text">
                        ${formatChangelogContent(section.content)}
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

// Initialize logging
function initializeLogging() {
    // Setup logging for the main application
    Utils.Logger.info('Shakshuka application initialized');
}

// Global functions that use AppState - no global variables needed

// Global CSRF token cache
window.csrfToken = null;

// Helper function to get CSRF token
async function getCSRFToken() {
    if (!window.csrfToken) {
        try {
            const response = await fetch('/api/csrf-token');
            const data = await response.json();
            window.csrfToken = data.csrf_token;
        } catch (error) {
            console.error('Failed to get CSRF token:', error);
            window.csrfToken = null;
        }
    }
    return window.csrfToken;
}

// Helper function to make authenticated requests with CSRF token
async function makeAuthenticatedRequest(url, options = {}) {
    const token = await getCSRFToken();
    console.log('CSRF Token:', token);
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'X-CSRF-Token': token })
        }
    };
    
    console.log('Request headers:', defaultOptions.headers);
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

        // Authentication Functions - Authentication disabled
        async function checkAuthStatus() {
            // Authentication disabled - just load the app
            console.log('Authentication disabled - loading app directly');
            initializeApp();
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
    safeAddEventListener('quick-add-btn', 'click', () => openTaskModal());
    safeAddEventListener('quick-add-btn', 'click', () => openQuickAddModal());
    
    // Modal controls
    safeAddEventListener('close-modal', 'click', () => closeTaskModal());
    safeAddEventListener('close-quick-modal', 'click', () => closeQuickAddModal());
    safeAddEventListener('cancel-task', 'click', () => closeTaskModal());
    safeAddEventListener('cancel-quick-task', 'click', () => closeQuickAddModal());
    
    // Form submissions
    safeAddEventListener('save-task', 'click', () => saveTask());
    safeAddEventListener('save-quick-task', 'click', () => saveQuickTask());
    
    // Changelog functionality
    safeAddEventListener('view-changelog-btn', 'click', () => openChangelogModal());
    safeAddEventListener('close-changelog-modal', 'click', () => closeChangelogModal());
    
    // User session management
    safeAddEventListener('clear-data-btn', 'click', () => {
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
    if (page === 'tasks') {
        loadTasks();
    } else if (page === 'planner') {
        // Load tasks first, then planner data will be loaded automatically
        loadTasks();
    } else if (page === 'analytics') {
        updateDashboardStats();
    } else if (page === 'settings') {
        loadSettingsPage();
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
            Utils.Logger.log(`Loaded ${AppState.getTasks().length} tasks`);
            showLoading(false); // Hide loading overlay on success
            return; // Success
            
        } catch (error) {
            Utils.Logger.error(`Load tasks attempt ${attempt} failed:`, error);
            
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
            
            console.log('Current page:', AppState.get('currentPage'));
            if (AppState.get('currentPage') === 'tasks') {
                console.log('Rendering tasks...');
                renderTasks();
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
            
            if (AppState.get('currentPage') === 'tasks') {
                renderTasks();
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
        Utils.Logger.log('Generated grid HTML');
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

// Create Tasks object with the modal functions for showAddTaskOptions
window.Tasks = {
    openTaskModal,
    openQuickAddModal,
    openScheduleModal,
    closeTaskModal,
    closeQuickAddModal,
    closeScheduleModal
};

function editTask(taskId) {
    openTaskModal(taskId);
}

async function undoCompleteTask(taskId) {
    await updateTask(taskId, { completed: false, completed_at: null });
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
    Utils.Logger.log('Setting up drag and drop...');
    
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
    Utils.Logger.log('Found draggable tasks:', draggableTasks.length);
    
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
    Utils.Logger.log('Found time slots:', timeContents.length);
    
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
    Utils.Logger.log('Found scheduled tasks:', scheduledTasks.length);
    
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
    
    // Store references to tasks that might need to be removed
    const scheduledTask = document.querySelector(`.scheduled-task[data-task-id="${taskId}"]`);
    const draggedTask = document.querySelector(`.draggable-task[data-task-id="${taskId}"]`);
    
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
            // Only remove tasks from DOM after successful API call
            if (scheduledTask) {
                scheduledTask.remove();
            }
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
        // Check if scheduled_hour exists and is valid
        if (!task.scheduled_hour || task.scheduled_hour === 'null' || task.scheduled_hour === 'undefined') {
            console.log(`Task ${task.title} has no valid scheduled_hour: ${task.scheduled_hour}`);
            return;
        }
        
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
        
        // Hide loading screen after settings are applied
        hideLoadingScreen();
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
            loadPlannerData(); // Reload entire planner
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
    // Authentication disabled - no special handling needed
    
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

async function checkGitHubUpdate() {
    try {
        const branch = document.getElementById('github-branch').value;
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
        const branch = document.getElementById('github-branch').value;
        showNotification('Downloading update from GitHub...', 'info');
        
        const response = await fetch('/api/github/download-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ branch: branch })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Update downloaded! Installation starting...', 'success');
            // Close any open modals
            closeUpdateModal();
            closeGitHubUpdateModal();
            
            // Show a message that the app will restart
            setTimeout(() => {
                showNotification('The application will restart after installation completes.', 'info');
            }, 2000);
        } else {
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
        <div id="github-update-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>GitHub Update</h2>
                    <button class="modal-close" id="close-github-update-modal">&times;</button>
                </div>
                <div id="github-update-info" class="modal-body">
                    <!-- Update info will be populated here -->
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="cancel-github-update">Cancel</button>
                    <button class="btn-primary" id="download-github-update">Download & Install</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHTML);
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
    const taskData = {
        title: document.getElementById('quick-task-title').value.trim(),
        description: '',
        project: '',
        estimated_duration: 60
    };
        
        console.log('Quick task data:', taskData);
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


