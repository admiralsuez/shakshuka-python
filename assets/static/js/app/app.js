// Main Shakshuka Application - Module Architecture

// Import all modules
// Note: These will be loaded in the HTML template in the correct order

// Setup all event listeners
// Page navigation
// Layout management
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
        if (Number.isNaN(interval)) {
            throw new Error('Invalid autosave interval');
        }

        const response = await apiCall('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({ autosave_interval: interval })
        });

        if (!response.ok) {
            throw new Error('Failed to update autosave interval');
        }

        try {
            const settings = AppState.get('currentSettings') || {};
            settings.autosave_interval = interval;
            AppState.set('currentSettings', settings);
        } catch (e) {}

        showNotification('Autosave interval updated successfully!', 'success');
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
        const d = new Date();
        const ds = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
        a.download = `shakshuka-backup-${ds}.json`;
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
            await AppState.setTasks([]);
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

// Backup and update modal functions


// Account management

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


// Load account settings

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
    
    // Show reset overlay animation
    if (typeof DailyResetOverlay !== 'undefined' && DailyResetOverlay.show) {
        DailyResetOverlay.showForDuration(2000);
    }
    
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
    
    // Logo click → ask for confirmation, then hard reload the app
    safeAddEventListener('app-logo', 'click', () => {
        const ok = window.confirm ? window.confirm('Reload Shakshuka now? This will refresh the app UI.') : true;
        if (ok) {
            window.location.reload();
        }
    });

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
    safeAddEventListener('view-whats-new-btn', 'click', () => showWhatsNewModalForLatestVersion({ markAsSeen: false }));
    
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
    safeAddEventListener('mini-analytics-interval', 'change', updateMiniAnalyticsInterval);
    safeAddEventListener('settings-layout', 'change', updateSettingsLayout);
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
    safeAddEventListener('close-strike-report-history-modal', 'click', closeStrikeReportHistoryModal);

    // Fallback: delegate strike button clicks to handle cases where inline handlers fail after navigation
    if (!window.__strikeDelegationSetup) {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.task-action.strike-btn, .task-action[title="Strike Task"]');
            if (!btn) return;
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
    safeAddEventListener('backup-before-update', 'change', updateUpdateSettings);
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
async function navigateToPage(page) {
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
        try {
            const currentTasks = (typeof AppState !== 'undefined' && typeof AppState.getTasks === 'function')
                ? (AppState.getTasks() || [])
                : ((AppState && AppState.get && AppState.get('tasks')) || []);
            if (currentTasks.length === 0 && typeof loadTasks === 'function') {
                await loadTasks();
            }
        } catch (e) { /* no-op */ }
        updateDashboardStats();

        // Strike Calendar (render/re-render on every Analytics navigation)
        try {
            if (window.AnalyticsExtras && window.AnalyticsExtras.StrikeCalendar) {
                await window.AnalyticsExtras.StrikeCalendar.init();
                if (typeof window.AnalyticsExtras.StrikeCalendar.load === 'function') {
                    const now = new Date();
                    const currentMonth = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
                    await window.AnalyticsExtras.StrikeCalendar.load(currentMonth);
                }
            }
        } catch (e) { /* no-op */ }
    } else if (page === 'settings') {
        loadSettingsPage();
        try {
            if (typeof window.bindShowRecapButton === 'function') {
                window.bindShowRecapButton();
            }
        } catch (e) { /* no-op */ }
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
// Missing utility functions
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

            await AppState.setTasks(merged);
            
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
            
            await updateDashboardStats();
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
    
    // Use sortTasksForDisplay from tasks.js if available, otherwise use default sorting
    let sortedTasks;
    if (window.Tasks && typeof window.Tasks.sortTasksForDisplay === 'function') {
        sortedTasks = window.Tasks.sortTasksForDisplay(filteredTasks);
    } else if (typeof sortTasksForDisplay === 'function') {
        sortedTasks = sortTasksForDisplay(filteredTasks);
    } else {
        // Fallback: Sort tasks with struck tasks at the bottom, due today at top
        const _today = new Date();
        const todayStr = `${_today.getFullYear()}-${String(_today.getMonth() + 1).padStart(2, '0')}-${String(_today.getDate()).padStart(2, '0')}`;
        sortedTasks = [...filteredTasks].sort((a, b) => {
            // First, handle struck_today so completed/struck tasks fall to the bottom
            if (a.struck_today && b.struck_today) return 0;
            if (a.struck_today) return 1;
            if (b.struck_today) return -1;

            // Within the same struck status, move tasks due today to the front of the queue
            const aDueToday = !a.struck_today && a.due_date && String(a.due_date).split('T')[0] === todayStr;
            const bDueToday = !b.struck_today && b.due_date && String(b.due_date).split('T')[0] === todayStr;

            if (aDueToday && !bDueToday) return -1;
            if (!aDueToday && bDueToday) return 1;

            return 0;
        });
    }
    
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
                    
                    const isTaskExpired = window.TaskHelpers && typeof window.TaskHelpers.isExpired === 'function' ? window.TaskHelpers.isExpired(task) : false;
                    
                    return `
                        <div class="task-card ${task.completed ? 'completed' : ''} ${task.struck_today ? 'struck-today' : ''} ${(task.struck_today && task.strike_count > 1) ? 'restrike' : ''}" data-task-id="${task.id}">
                            <div class="task-actions-top-left">
                                ${task.struck_today && !task.completed ? `
                                    <button class="task-action undo-action" onclick="undoStrike('${task.id}')" title="Undo Strike">
                                        <i class="fas fa-undo"></i>
                                    </button>
                                ` : ''}
                                ${isTaskExpired && !task.completed ? `
                                    <button class="task-action retry-btn" onclick="retryTask('${task.id}')" title="Retry Task">
                                        <i class="fas fa-redo"></i>
                                    </button>
                                    <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                                        <i class="fas fa-check"></i>
                                    </button>
                                ` : !task.completed && canStrikeTask(task) ? `
                                    <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                                        <i class="fas fa-check"></i>
                                    </button>
                                ` : !task.completed ? `
                                    <button class="task-action strike-btn disabled" title="Maximum strikes reached for today" disabled>
                                        <i class="fas fa-check"></i>
                                    </button>
                                ` : ''}
                                <button class="task-action" onclick="openStrikeReportHistoryModal('${task.id}')" title="Report History">
                                    <i class="fas fa-clipboard-list"></i>
                                </button>
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
                                <h3 class="task-title-main ${task.struck_today ? 'struck-today' : ''}">
                                    ${sanitizeHTML(task.title)}
                                    ${typeof RefreshedBadgeHelper !== 'undefined' ? RefreshedBadgeHelper.getBadgeHTML(task) : ''}
                                </h3>
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
                    ${hasDescription ? `<button class="task-title-more" onclick="openTaskDetailsModal('${task.id}')" title="View details"><i class="fas fa-chevron-right"></i></button>` : ''}
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
                ${typeof RefreshedBadgeHelper !== 'undefined' ? RefreshedBadgeHelper.getBadgeHTML(task) : ''}
                ${(() => {
                    const isTaskExpired = window.TaskHelpers && typeof window.TaskHelpers.isExpired === 'function' ? window.TaskHelpers.isExpired(task) : false;
                    if (isTaskExpired && !task.completed) {
                        return `<button class="task-action retry-btn" onclick="retryTask('${task.id}')" title="Retry Task">
                            <i class="fas fa-redo"></i>
                        </button>
                        <button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                            <i class="fas fa-check"></i>
                        </button>`;
                    } else if (!task.completed && canStrikeTask(task)) {
                        return `<button class="task-action strike-btn" onclick="openStrikeModal('${task.id}')" title="Strike Task">
                            <i class="fas fa-check"></i>
                        </button>`;
                    } else if (!task.completed) {
                        return `<button class="task-action strike-btn disabled" title="Maximum strikes reached for today" disabled>
                            <i class="fas fa-check"></i>
                        </button>`;
                    }
                    return '';
                })()}
                <button class="task-action" onclick="openStrikeReportHistoryModal('${task.id}')" title="Report History">
                    <i class="fas fa-clipboard-list"></i>
                </button>
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

// Modal Functions

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

// Form Submissions


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
        const settingsLayoutEl = document.getElementById('settings-layout');
        if (settingsLayoutEl) settingsLayoutEl.value = settings.settings_layout || 'scroll';
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

        try {
            if (window.Settings && typeof window.Settings.applySettingsLayout === 'function') {
                window.Settings.applySettingsLayout();
            }
        } catch (e) {}
        
        // Hide loading screen after settings are applied
        hideLoadingScreen();

        // After settings + theme are ready, show one-time "What's New" modal if needed
        try {
            maybeShowWhatsNewModal();
        } catch (e) {
            console.error('Error showing What\'s New modal:', e);
        }

        // Also perform a lightweight weekly GitHub update check on launch.
        try {
            maybeAutoCheckForUpdatesWeekly();
        } catch (e) {
            console.error('Error running weekly auto-update check:', e);
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
    },
    'yellow': {
        'primary-gradient': 'linear-gradient(135deg, #FFE066, #FFC107)',
        'secondary-gradient': 'linear-gradient(135deg, #FFFDE7 0%, #FFF3CD 100%)',
        'background-color': '#FFFDE7',
        'surface-color': 'rgba(255, 255, 255, 0.95)',
        'text-color': '#5C4A00',
        'text-secondary': '#8D6E63',
        'border-color': 'rgba(255, 193, 7, 0.3)',
        'shadow-color': 'rgba(255, 193, 7, 0.1)',
        'accent-color': '#FFC107'
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
    
    // Apply intensity variations for yellow theme
    if (theme === 'yellow' && intensity !== '5') {
        const intensityMap = {
            '1': 'linear-gradient(135deg, #FFF3CD, #FFE082)',
            '2': 'linear-gradient(135deg, #FFECB3, #FFD54F)',
            '3': 'linear-gradient(135deg, #FFE082, #FFC107)',
            '4': 'linear-gradient(135deg, #FFD54F, #FFB300)',
            '6': 'linear-gradient(135deg, #FFC107, #FFB300)',
            '7': 'linear-gradient(135deg, #FFB300, #FFA000)',
            '8': 'linear-gradient(135deg, #FFA000, #FF8F00)',
            '9': 'linear-gradient(135deg, #FF8F00, #FF6F00)',
            '10': 'linear-gradient(135deg, #FF6F00, #E65100)'
        };
        if (intensityMap[intensity]) {
            themeColors.yellow['primary-gradient'] = intensityMap[intensity];
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

// Schedule Modal Functions

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
// New Functions for Shakshuka Features


// Layout Functions
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

// Duplicate functions removed - using the ones defined earlier in the file around line 414-420

// Analytics dashboard updater

// Account Management Functions

// ========================================
// GLOBAL API CALL HELPER WITH CREDENTIALS
// ========================================
// Helper function for authenticated API calls with credentials
// This replaces makeAuthenticatedRequest with better FormData handling
async function apiCall(url, options = {}) {
    if (window.Utils && typeof window.Utils.apiCall === 'function') {
        return window.Utils.apiCall(url, options);
    }
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
