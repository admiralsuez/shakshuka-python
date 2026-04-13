/**
 * Settings Module
 * Handles all settings-related functionality including:
 * - Loading and saving settings
 * - Theme management and application
 * - DPI scaling
 * - Autostart configuration
 * - Auto-save interval
 * Version: 3.0.3
 */

// Track settings changes
window.incrementSettingsChangeCount = function incrementSettingsChangeCount() {
    try {
        const k = 'settings_changes_count';
        const n = parseInt(localStorage.getItem(k) || '0', 10) + 1;
        localStorage.setItem(k, String(n));
        if (typeof updateDashboardStats === 'function') updateDashboardStats();
    } catch (e) { /* ignore */ }
};

const Settings = {
    _initializing: true,

    _getCurrentSettings() {
        try {
            if (typeof AppState !== 'undefined' && AppState && typeof AppState.get === 'function') {
                return AppState.get('currentSettings') || {};
            }
        } catch (e) { /* no-op */ }
        return {};
    },

    _setCurrentSettings(settings) {
        try {
            if (typeof AppState !== 'undefined' && AppState) {
                // Use synchronous setter when available to avoid race conditions
                if (typeof AppState.setSync === 'function') {
                    AppState.setSync('currentSettings', settings);
                } else if (typeof AppState.set === 'function') {
                    // Fall back to async setter
                    AppState.set('currentSettings', settings);
                }
            }
        } catch (e) { /* no-op */ }
    },

    /**
     * Merge server-returned settings with existing settings and the local patch.
     * This makes Perf Max work even if the backend ignores/does not echo perf flags.
     */
    _mergeSettings(serverSettings, patch) {
        // Use Settings._getCurrentSettings directly to avoid relying on `this` binding
        const current    = (typeof Settings !== 'undefined' && Settings && typeof Settings._getCurrentSettings === 'function')
            ? Settings._getCurrentSettings() || {}
            : {};
        const fromServer = serverSettings || {};
        const fromPatch  = patch || {};
        return Object.assign({}, current, fromServer, fromPatch);
    },

    async _putSettings(patch) {
        if (!window.Utils || typeof window.Utils.apiRequestJson !== 'function') {
            const response = await apiCall('/api/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patch || {})
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.error || 'Failed to update settings');
            }
            return await response.json();
        }

        return await window.Utils.apiRequestJson(
            '/api/settings',
            {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(patch || {})
            },
            { expectObject: true, retries: 0 }
        );
    },
    /**
     * Load settings from server and apply them
     */
    async load() {
        // Guard to prevent change handlers from saving defaults during init
        this._initializing = true;
        try {
            try {
                if (window.Utils && typeof window.Utils.waitForHealthy === 'function') {
                    await window.Utils.waitForHealthy({ timeoutMs: 12000, intervalMs: 250 });
                }
            } catch (e) {}

            let settings = null;
            if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
                settings = await window.Utils.apiRequestJson('/api/settings', {}, { expectObject: true, retries: 3, retryDelayMs: 750 });
            } else {
                const response = await apiCall('/api/settings');
                if (!response.ok) {
                    throw new Error('Failed to load settings');
                }
                settings = await response.json();
            }
            this._setCurrentSettings(settings);
            
            // Update UI elements
            const autostartToggle = document.getElementById('autostart-toggle');
            const autosaveInterval = document.getElementById('autosave-interval');
            const miniAnalyticsInterval = document.getElementById('mini-analytics-interval');
            const themeSelector = document.getElementById('theme-selector');
            const finishSelector = document.getElementById('finish-selector');
            const intensitySelector = document.getElementById('intensity-selector');
            const dpiSelector = document.getElementById('dpi-selector');
            const settingsLayout = document.getElementById('settings-layout');
            const quickProjectToggle = document.getElementById('quick-project-from-title');
            const casualDatesToggle = document.getElementById('casual-dates-toggle');
            const hourSelect = document.getElementById('reset-hour-select');
            const minuteSelect = document.getElementById('reset-minute-select');
            const periodSelect = document.getElementById('reset-period-select');
            const streakSkipWeekends = document.getElementById('streak-skip-weekends');
            const streakCountNewTasks = document.getElementById('streak-count-new-tasks');
            const streakCountSettings = document.getElementById('streak-count-settings');
            const perfDisableBlur = document.getElementById('perf-disable-blur');
            const perfDisableShadows = document.getElementById('perf-disable-shadows');
            const perfDisableAnimations = document.getElementById('perf-disable-animations');
            const perfDisableGlow = document.getElementById('perf-disable-glow');
            const compactModeToggle = document.getElementById('compact-mode-toggle');
            
            // Backend returns autostart_enabled; keep legacy "autostart" fallback just in case
            if (autostartToggle) {
                autostartToggle.checked = (typeof settings.autostart_enabled === 'boolean')
                    ? settings.autostart_enabled
                    : (settings.autostart || false);
            }
            if (autosaveInterval) autosaveInterval.value = settings.autosave_interval || 30;
            if (miniAnalyticsInterval) miniAnalyticsInterval.value = (settings.mini_analytics_interval ?? 5);
            if (themeSelector) themeSelector.value = settings.theme || 'light';
            if (finishSelector) finishSelector.value = settings.finish || 'glossy';
            if (intensitySelector) intensitySelector.value = settings.intensity || '5';
            if (dpiSelector) dpiSelector.value = settings.dpi_scale || 100;
            if (settingsLayout) settingsLayout.value = settings.settings_layout || 'scroll';
            if (quickProjectToggle) quickProjectToggle.checked = !!settings.quick_project_from_title;
            if (casualDatesToggle) casualDatesToggle.checked = !!settings.casual_dates;
            if (streakSkipWeekends) streakSkipWeekends.checked = !!settings.streak_skip_weekends;
            if (streakCountNewTasks) streakCountNewTasks.checked = !!settings.streak_count_new_tasks;
            if (streakCountSettings) streakCountSettings.checked = !!settings.streak_count_settings;
            if (perfDisableBlur) perfDisableBlur.checked = !!settings.perf_disable_blur;
            if (perfDisableShadows) perfDisableShadows.checked = !!settings.perf_disable_shadows;
            if (perfDisableAnimations) perfDisableAnimations.checked = !!settings.perf_disable_animations;
            if (perfDisableGlow) perfDisableGlow.checked = !!settings.perf_disable_glow;
            if (compactModeToggle) compactModeToggle.checked = !!settings.compact_mode;

            // New settings (v25.3)
            const defaultTaskDuration = document.getElementById('default-task-duration');
            const startPageSelect = document.getElementById('start-page-select');
            const notificationSoundToggle = document.getElementById('notification-sound-toggle');
            const weekStartDaySelect = document.getElementById('week-start-day-select');
            if (defaultTaskDuration) defaultTaskDuration.value = settings.default_task_duration || 60;
            if (startPageSelect) startPageSelect.value = settings.start_page || 'tasks';
            if (notificationSoundToggle) notificationSoundToggle.checked = !!settings.notification_sound;
            if (weekStartDaySelect) weekStartDaySelect.value = String(settings.week_start_day ?? 1);

            // Apply start page on initial load (navigate to the configured start page)
            try {
                const sp = settings.start_page || 'tasks';
                if (sp !== 'tasks' && typeof window.navigateTo === 'function') {
                    window.navigateTo(sp);
                } else if (sp !== 'tasks') {
                    // Fallback: click the nav item
                    const navItem = document.querySelector(`.nav-item[data-page="${sp}"]`);
                    if (navItem) navItem.click();
                }
            } catch (e) { /* no-op */ }

            // Sync Perf Max button label with current state
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
 
            // Build selects (once)
            this.ensureTimeSelectOptions();
            
            if (hourSelect && minuteSelect) {
                const timeStr = settings.daily_reset_time || '06:00';
                console.log('[DEBUG] Loading reset time from settings:', timeStr);
                const [hours24, minutes] = timeStr.split(':').map(Number);
                console.log('[DEBUG] Parsed hours24:', hours24, 'minutes:', minutes);
                const { hour12, period } = Settings.convert24to12(hours24);
                console.log('[DEBUG] Converted to 12-hour:', { hour12, period });
                hourSelect.value = String(hour12).padStart(2, '0');
                const minuteVal = (parseInt(minutes, 10) - (parseInt(minutes, 10) % 5)).toString().padStart(2, '0');
                minuteSelect.value = minuteVal;
                if (periodSelect) periodSelect.value = period;
                console.log('[DEBUG] Set UI values - hour:', hourSelect.value, 'minute:', minuteSelect.value, 'period:', periodSelect.value);
            }
            
            this.applyThemeAndDPI();
            this.applySettingsLayout();
            
            // Ensure daily reset timer uses latest settings
            if (typeof window.setupDailyReset === 'function') {
                window.setupDailyReset();
            }
            
            // Hide loading screen after settings are applied
            if (typeof hideLoadingScreen === 'function') {
                hideLoadingScreen();
            }
            // End init phase
            this._initializing = false;
            console.log('[DEBUG] Settings initialization complete, _initializing set to false');
            
            // Re-bind reset time handlers after initialization
            if (typeof window._bindResetTimeHandlers === 'function') {
                console.log('[DEBUG] Re-binding reset time handlers after init');
                setTimeout(() => window._bindResetTimeHandlers(), 100);
            }
        } catch (error) {
            Utils.Logger.error('Error loading settings:', error);
            // Hide loading screen even if there's an error
            if (typeof hideLoadingScreen === 'function') {
                hideLoadingScreen();
            }
            // End init phase on error as well
            this._initializing = false;
            console.log('[DEBUG] Settings initialization complete (with error), _initializing set to false');
            
            // Re-bind reset time handlers after initialization even on error
            if (typeof window._bindResetTimeHandlers === 'function') {
                console.log('[DEBUG] Re-binding reset time handlers after init (error path)');
                setTimeout(() => window._bindResetTimeHandlers(), 100);
            }
        }
    },

    async updateSettingsLayout() {
        const el = document.getElementById('settings-layout');
        const layout = el ? el.value : 'scroll';

        const prev = (this._getCurrentSettings().settings_layout || 'scroll');

        try {
            const updated = await this._putSettings({ settings_layout: layout });
            this._setCurrentSettings(updated);
            window.incrementSettingsChangeCount?.();
            this.applySettingsLayout();
        } catch (error) {
            Utils.Logger.error('Error updating settings layout:', error);
            if (el) el.value = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating settings layout', 'error');
            }
        }
    },

    applySettingsLayout() {
        const settings = this._getCurrentSettings();
        const layout = (settings.settings_layout === 'tabs') ? 'tabs' : 'scroll';

        const settingsPage = document.getElementById('settings-page');
        const container = settingsPage ? settingsPage.querySelector('.settings-container') : null;
        if (!container) return;

        const sections = Array.from(container.querySelectorAll('.settings-section'));
        if (!sections.length) return;

        const existingTabs = container.querySelector('.settings-tabs');
        if (layout !== 'tabs') {
            if (existingTabs) existingTabs.remove();
            sections.forEach((s) => s.classList.remove('settings-section-hidden'));
            return;
        }

        const tabs = existingTabs || document.createElement('div');
        tabs.className = 'settings-tabs';
        tabs.innerHTML = '';

        const activeAttr = container.getAttribute('data-settings-active-tab');
        let activeIndex = 0;
        try {
            activeIndex = activeAttr ? parseInt(activeAttr, 10) : 0;
        } catch (e) {
            activeIndex = 0;
        }
        if (!Number.isFinite(activeIndex) || activeIndex < 0 || activeIndex >= sections.length) {
            activeIndex = 0;
        }

        const setActive = (idx) => {
            container.setAttribute('data-settings-active-tab', String(idx));
            sections.forEach((s, i) => {
                s.classList.toggle('settings-section-hidden', i !== idx);
            });
            Array.from(tabs.querySelectorAll('.settings-tab-btn')).forEach((b, i) => {
                b.classList.toggle('active', i === idx);
            });
        };

        sections.forEach((section, idx) => {
            const h = section.querySelector('h3');
            const title = h ? (h.textContent || '').trim() : `Section ${idx + 1}`;
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'settings-tab-btn';
            btn.textContent = title || `Section ${idx + 1}`;
            btn.addEventListener('click', () => setActive(idx));
            tabs.appendChild(btn);
        });

        if (!existingTabs) {
            container.insertBefore(tabs, container.firstChild);
        }
        setActive(activeIndex);
    },

    async updateMiniAnalyticsInterval() {
        const el = document.getElementById('mini-analytics-interval');
        const valRaw = el ? el.value : '5';
        let interval = 5;
        try {
            interval = parseInt(valRaw, 10);
        } catch (e) {
            interval = 5;
        }

        const prev = (this._getCurrentSettings().mini_analytics_interval ?? 5);

        try {
            const updated = await this._putSettings({ mini_analytics_interval: interval });
            this._setCurrentSettings(updated);
            window.incrementSettingsChangeCount?.();
            try {
                if (window.MiniAnalyticsTicker && typeof window.MiniAnalyticsTicker.applyIntervalFromSettings === 'function') {
                    window.MiniAnalyticsTicker.applyIntervalFromSettings();
                }
            } catch (e) { /* no-op */ }
        } catch (error) {
            Utils.Logger.error('Error updating mini analytics interval:', error);
            if (el) el.value = String(prev);
            if (typeof showNotification === 'function') {
                showNotification('Error updating mini analytics interval', 'error');
            }
        }
    },

    /**
     * Update autostart setting
     */
    async updateAutostart() {
        const toggle = document.getElementById('autostart-toggle');
        const enabled = !!toggle?.checked;
        const prev = !!(this._getCurrentSettings().autostart_enabled ?? this._getCurrentSettings().autostart);
        
        try {
            const updated = await this._putSettings({ autostart: enabled });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification(
                    enabled ? 'Autostart enabled' : 'Autostart disabled',
                    'success'
                );
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating autostart:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating autostart setting', 'error');
            }
        }
    },

    /**
     * Update quick project-from-title toggle
     */
    async updateQuickProjectFromTitle() {
        const toggle = document.getElementById('quick-project-from-title');
        const enabled = !!toggle?.checked;
        const prev = !!this._getCurrentSettings().quick_project_from_title;
        
        try {
            const updated = await this._putSettings({ quick_project_from_title: enabled });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification(
                    enabled
                        ? 'Quick project from title enabled (first word before comma)'
                        : 'Quick project from title disabled',
                    'success'
                );
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating quick project-from-title setting:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating quick project setting', 'error');
            }
        }
    },

    /**
     * Update casual dates toggle
     */
    async updateCasualDates() {
        const toggle = document.getElementById('casual-dates-toggle');
        const enabled = !!toggle?.checked;
        const prev = !!this._getCurrentSettings().casual_dates;

        try {
            const updated = await this._putSettings({ casual_dates: enabled });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification(
                    enabled
                        ? 'Casual dates enabled (today, in 2 days, this weekend)'
                        : 'Casual dates disabled',
                    'success'
                );
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating casual dates setting:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating casual date setting', 'error');
            }
        }
    },

    /**
     * Update streak skip weekends setting
     */
    async updateStreakSkipWeekends() {
        const toggle = document.getElementById('streak-skip-weekends');
        const enabled = !!toggle?.checked;
        const prev = !!this._getCurrentSettings().streak_skip_weekends;

        try {
            const updated = await this._putSettings({ streak_skip_weekends: enabled });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Weekends will be skipped in streak' : 'Weekends count in streak', 'success');
            }
            window.incrementSettingsChangeCount?.();
            if (typeof updateDashboardStats === 'function') updateDashboardStats();
        } catch (error) {
            Utils.Logger.error('Error updating streak skip weekends:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating streak setting', 'error');
            }
        }
    },

    /**
     * Update streak count new tasks setting
     */
    async updateStreakCountNewTasks() {
        const toggle = document.getElementById('streak-count-new-tasks');
        const enabled = !!toggle?.checked;
        const prev = !!this._getCurrentSettings().streak_count_new_tasks;

        try {
            const updated = await this._putSettings({ streak_count_new_tasks: enabled });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Adding tasks counts as streak activity' : 'Adding tasks won\'t count as streak activity', 'success');
            }
            window.incrementSettingsChangeCount?.();
            if (typeof updateDashboardStats === 'function') updateDashboardStats();
        } catch (error) {
            Utils.Logger.error('Error updating streak count new tasks:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating streak setting', 'error');
            }
        }
    },

    /**
     * Update streak count settings changes setting
     */
    async updateStreakCountSettings() {
        const toggle = document.getElementById('streak-count-settings');
        const enabled = !!toggle?.checked;
        const prev = !!this._getCurrentSettings().streak_count_settings;

        try {
            const updated = await this._putSettings({ streak_count_settings: enabled });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Settings changes count as streak activity' : 'Settings changes won\'t count as streak activity', 'success');
            }
            window.incrementSettingsChangeCount?.();
            if (typeof updateDashboardStats === 'function') updateDashboardStats();
        } catch (error) {
            Utils.Logger.error('Error updating streak count settings:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating streak setting', 'error');
            }
        }
    },

    /**
     * Update compact mode layout setting
     */
    async updateCompactMode() {
        const toggle = document.getElementById('compact-mode-toggle');
        const enabled = !!toggle?.checked;
        const prev = !!this._getCurrentSettings().compact_mode;

        try {
            const patch = { compact_mode: enabled };
            const serverSettings = await this._putSettings(patch);
            const merged = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);
            this.applyThemeAndDPI();

            // Best-effort persistence checker: re-fetch settings and ensure compact_mode matches.
            try {
                if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
                    const verify = await window.Utils.apiRequestJson('/api/settings', {}, { expectObject: true, retries: 1, retryDelayMs: 500 });
                    if (verify && typeof verify.compact_mode !== 'undefined' && !!verify.compact_mode !== enabled) {
                        // Log a soft warning so issues surface in dev tools without breaking UX.
                        console.warn('[Settings] compact_mode persistence mismatch', {
                            expected: enabled,
                            server: verify.compact_mode,
                        });
                    }
                }
            } catch (e) {
                // Non-fatal: just log to console.
                console.warn('[Settings] compact_mode persistence check failed', e);
            }

            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Compact mode enabled' : 'Compact mode disabled', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating compact mode:', error);
            if (toggle) toggle.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating compact mode', 'error');
            }
        }
    },

    /**
     * Update autosave interval setting
     */
    async updateAutosaveInterval() {
        const el = document.getElementById('autosave-interval');
        const interval = parseInt(el?.value);
        const prev = (this._getCurrentSettings().autosave_interval || 30);
        
        try {
            const updated = await this._putSettings({ autosave_interval: interval });
            this._setCurrentSettings(updated);
            if (typeof showNotification === 'function') {
                showNotification('Auto-save interval updated', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating autosave interval:', error);
            if (el) el.value = String(prev);
            if (typeof showNotification === 'function') {
                showNotification('Error updating auto-save interval', 'error');
            }
        }
    },

    /**
     * Apply theme and DPI settings to the page
     */
    applyThemeAndDPI() {
        const settings = this._getCurrentSettings();
        const theme = settings.theme || 'light';
        // Speedy theme always renders as matte to minimize heavy visual effects.
        const finish = theme === 'speedy' ? 'matte' : (settings.finish || 'glossy');
        const intensity = settings.intensity || '5';
        const dpiScale = settings.dpi_scale || 100;
        const compactMode = !!settings.compact_mode;
        
        // Apply theme
        document.body.setAttribute('data-theme', theme);
        
        // Apply finish
        document.body.setAttribute('data-finish', finish);
        
        // Apply intensity
        document.body.setAttribute('data-intensity', intensity);
        
        // Apply compact layout flag for CSS
        if (compactMode) {
            document.body.setAttribute('data-compact', 'on');
        } else {
            document.body.removeAttribute('data-compact');
        }
        
        // Apply DPI scaling (convert percentage to decimal)
        document.documentElement.style.setProperty('--dpi-scale', (dpiScale / 100));
        
        // Update CSS custom properties based on theme
        this.updateThemeCSSVariables(theme, intensity);
    },

    /**
     * Update CSS variables based on theme and intensity
     */
    updateThemeCSSVariables(theme, intensity) {
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
            },
            'speedy': {
                'primary-gradient': 'linear-gradient(135deg, #1F2933, #1B1F2A)',
                'secondary-gradient': 'linear-gradient(135deg, #111827 0%, #111827 100%)',
                'background-color': '#0B1120',
                'surface-color': 'rgba(15, 23, 42, 0.98)',
                'text-color': '#E5E7EB',
                'text-secondary': '#9CA3AF',
                'border-color': 'rgba(148, 163, 184, 0.35)',
                'shadow-color': 'rgba(15, 23, 42, 0.4)',
                'accent-color': '#22C55E'
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
        
        // Apply additional CSS custom properties
        const settings = this._getCurrentSettings();
        const dpiScale = settings.dpi_scale || 100;
        const perfDisableBlur = !!settings.perf_disable_blur;
        const perfDisableShadows = !!settings.perf_disable_shadows;
        const perfDisableAnimations = !!settings.perf_disable_animations;
        const perfDisableGlow = !!settings.perf_disable_glow;

        // If shadows are disabled, neutralize shadow color
        if (perfDisableShadows) {
            colors['shadow-color'] = 'rgba(0, 0, 0, 0)';
        }

        // If glow is disabled, flatten glossy overlay; otherwise restore CSS-defined default
        if (perfDisableGlow) {
            root.style.setProperty('--glossy-overlay', 'transparent');
            body.style.setProperty('--glossy-overlay', 'transparent');
        } else {
            // Remove inline override so base theme/finish CSS can re-apply the correct overlay
            root.style.removeProperty('--glossy-overlay');
            body.style.removeProperty('--glossy-overlay');
        }

        const additionalProperties = {
            'surface-finish-gradient': colors['secondary-gradient'],
            'box-shadow-primary': perfDisableShadows
                ? 'none'
                : `0 ${4 * (dpiScale / 100)}px ${12 * (dpiScale / 100)}px ${colors['shadow-color']}`,
            'border-finish': `1px solid ${colors['border-color']}`,
            'backdrop-filter': perfDisableBlur ? 'none' : 'blur(10px)',
            'text-primary': colors['text-color'],
            'text-secondary': colors['text-secondary'],
            'accent-gradient': colors['primary-gradient']
        };
        
        // Set CSS custom properties on both root and body
        Object.entries(additionalProperties).forEach(([property, value]) => {
            root.style.setProperty(`--${property}`, value);
            body.style.setProperty(`--${property}`, value);
        });

        // Body attributes used by CSS to hard-disable animations and effects
        if (perfDisableBlur) {
            body.setAttribute('data-perf-blur', 'off');
        } else {
            body.removeAttribute('data-perf-blur');
        }
        if (perfDisableShadows) {
            body.setAttribute('data-perf-shadow', 'off');
        } else {
            body.removeAttribute('data-perf-shadow');
        }
        if (perfDisableAnimations) {
            body.setAttribute('data-perf-anim', 'off');
        } else {
            body.removeAttribute('data-perf-anim');
        }
        if (perfDisableGlow) {
            body.setAttribute('data-perf-glow', 'off');
        } else {
            body.removeAttribute('data-perf-glow');
        }
    },

    /**
     * Update theme setting
     */
    async updateTheme() {
        const el = document.getElementById('theme-selector');
        const theme = el ? el.value : 'light';
        const prev = (this._getCurrentSettings().theme || 'light');
        
        try {
            let patch = { theme };
            // Speedy theme: apply performance-friendly defaults together with theme.
            if (theme === 'speedy') {
                patch = {
                    theme: 'speedy',
                    finish: 'matte',
                    intensity: '4',
                    perf_disable_blur: true,
                    perf_disable_shadows: true,
                    perf_disable_animations: true,
                    perf_disable_glow: true,
                };
            }
            const serverSettings = await this._putSettings(patch);
            const merged         = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);
            this.applyThemeAndDPI();
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
            if (typeof showNotification === 'function') {
                showNotification('Theme updated', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating theme:', error);
            if (el) el.value = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating theme', 'error');
            }
        }
    },

    /**
     * Update finish setting
     */
    async updateFinish() {
        const el = document.getElementById('finish-selector');
        const finish = el ? el.value : 'glossy';
        const prev = (this._getCurrentSettings().finish || 'glossy');
        
        try {
            const updated = await this._putSettings({ finish: finish });
            this._setCurrentSettings(updated);
            this.applyThemeAndDPI();
            if (typeof showNotification === 'function') {
                showNotification('Finish updated', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating finish:', error);
            if (el) el.value = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating finish', 'error');
            }
        }
    },

    /**
     * Update intensity setting
     */
    async updateIntensity() {
        const el = document.getElementById('intensity-selector');
        const intensity = el ? el.value : '5';
        const prev = (this._getCurrentSettings().intensity || '5');
        
        try {
            const updated = await this._putSettings({ intensity: intensity });
            this._setCurrentSettings(updated);
            this.applyThemeAndDPI();
            if (typeof showNotification === 'function') {
                showNotification('Intensity updated', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating intensity:', error);
            if (el) el.value = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating intensity', 'error');
            }
        }
    },

    /**
     * Update DPI scale setting
     */
    async updateDPI() {
        const el = document.getElementById('dpi-selector');
        const dpiScale = parseInt(el?.value);
        const prev = (this._getCurrentSettings().dpi_scale || 100);
        
        try {
            const updated = await this._putSettings({ dpi_scale: dpiScale });
            this._setCurrentSettings(updated);
            this.applyThemeAndDPI();
            if (typeof showNotification === 'function') {
                showNotification('DPI scale updated', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating DPI scale:', error);
            if (el) el.value = String(prev);
            if (typeof showNotification === 'function') {
                showNotification('Error updating DPI scale', 'error');
            }
        }
    },

    /**
     * Update Perf Max button label based on current perf flags.
     * When all perf_disable_* flags are enabled, show "Restore animations"; otherwise "Apply max".
     */
    updatePerfMaxButtonLabel() {
        try {
            const btn = document.getElementById('perf-max-button');
            if (!btn) return;
            const settings = this._getCurrentSettings() || {};
            const allOn = !!settings.perf_disable_blur &&
                          !!settings.perf_disable_shadows &&
                          !!settings.perf_disable_animations &&
                          !!settings.perf_disable_glow;
            btn.textContent = allOn ? 'Restore animations' : 'Apply max';
        } catch (e) { /* no-op */ }
    },
 
    /**
     * One-click Perf Max preset (Chrome / low FPS)
     *
     * Behaves as a toggle:
     * - If ALL perf_disable_* flags are currently enabled, clicking will
     *   restore animations/effects to their defaults (set all to false).
     * - Otherwise, clicking will enable Perf Max (set all to true).
     */
    async applyPerfMaxPreset() {
        try {
            const current = this._getCurrentSettings() || {};
            const allOn = !!current.perf_disable_blur &&
                          !!current.perf_disable_shadows &&
                          !!current.perf_disable_animations &&
                          !!current.perf_disable_glow;

            // Decide whether we are enabling Perf Max or restoring defaults
            let patch;
            let message;
            if (allOn) {
                // Restore animations / visual effects to default
                patch = {
                    perf_disable_blur:       false,
                    perf_disable_shadows:    false,
                    perf_disable_animations: false,
                    perf_disable_glow:       false,
                };
                message = 'Animations and visual effects restored to default';
            } else {
                // Enable Perf Max
                patch = {
                    perf_disable_blur:       true,
                    perf_disable_shadows:    true,
                    perf_disable_animations: true,
                    perf_disable_glow:       true,
                };
                message = 'Perf Max enabled (blurs, glows, and animations reduced)';
            }

            const serverSettings = await this._putSettings(patch);
            const merged         = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);

            // Reflect in UI toggles immediately using merged state
            try {
                const blurEl   = document.getElementById('perf-disable-blur');
                const shadowEl = document.getElementById('perf-disable-shadows');
                const animEl   = document.getElementById('perf-disable-animations');
                const glowEl   = document.getElementById('perf-disable-glow');
                if (blurEl)   blurEl.checked   = !!merged.perf_disable_blur;
                if (shadowEl) shadowEl.checked = !!merged.perf_disable_shadows;
                if (animEl)   animEl.checked   = !!merged.perf_disable_animations;
                if (glowEl)   glowEl.checked   = !!merged.perf_disable_glow;
            } catch (e) { /* no-op */ }

            // Update button label to reflect Perf Max state
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
 
            // Re-apply theme and performance-related CSS overrides
            this.applyThemeAndDPI();

            if (typeof showNotification === 'function') {
                showNotification(message, 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error applying Perf Max preset:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error applying Perf Max preset', 'error');
            }
        }
    },

    async updatePerfDisableBlur() {
        const el      = document.getElementById('perf-disable-blur');
        const enabled = !!el?.checked;
        const prev    = !!this._getCurrentSettings().perf_disable_blur;
        try {
            const patch          = { perf_disable_blur: enabled };
            const serverSettings = await this._putSettings(patch);
            const merged         = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);
            this.applyThemeAndDPI();
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Blur effects disabled' : 'Blur effects enabled', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating perf blur setting:', error);
            if (el) el.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating blur setting', 'error');
            }
        }
    },

    async updatePerfDisableShadows() {
        const el      = document.getElementById('perf-disable-shadows');
        const enabled = !!el?.checked;
        const prev    = !!this._getCurrentSettings().perf_disable_shadows;
        try {
            const patch          = { perf_disable_shadows: enabled };
            const serverSettings = await this._putSettings(patch);
            const merged         = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);
            this.applyThemeAndDPI();
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Shadows and heavy glows disabled' : 'Shadows enabled', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating perf shadows setting:', error);
            if (el) el.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating shadows setting', 'error');
            }
        }
    },

    async updatePerfDisableAnimations() {
        const el      = document.getElementById('perf-disable-animations');
        const enabled = !!el?.checked;
        const prev    = !!this._getCurrentSettings().perf_disable_animations;
        try {
            const patch          = { perf_disable_animations: enabled };
            const serverSettings = await this._putSettings(patch);
            const merged         = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);
            this.applyThemeAndDPI();
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Most UI animations disabled' : 'Animations enabled', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating perf animations setting:', error);
            if (el) el.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating animations setting', 'error');
            }
        }
    },

    async updatePerfDisableGlow() {
        const el      = document.getElementById('perf-disable-glow');
        const enabled = !!el?.checked;
        const prev    = !!this._getCurrentSettings().perf_disable_glow;
        try {
            const patch          = { perf_disable_glow: enabled };
            const serverSettings = await this._putSettings(patch);
            const merged         = Settings._mergeSettings(serverSettings, patch);
            this._setCurrentSettings(merged);
            this.applyThemeAndDPI();
            try { this.updatePerfMaxButtonLabel(); } catch (e) { /* no-op */ }
            if (typeof showNotification === 'function') {
                showNotification(enabled ? 'Glossy overlays disabled' : 'Glossy overlays enabled', 'success');
            }
            window.incrementSettingsChangeCount?.();
        } catch (error) {
            Utils.Logger.error('Error updating perf glow setting:', error);
            if (el) el.checked = prev;
            if (typeof showNotification === 'function') {
                showNotification('Error updating glow setting', 'error');
            }
        }
    },

    /**
     * Ensure time select options (hours 00-23, minutes 00,05,...,55)
     */
    ensureTimeSelectOptions() {
        const hourSelect = document.getElementById('reset-hour-select');
        const minuteSelect = document.getElementById('reset-minute-select');
        const periodSelect = document.getElementById('reset-period-select');
        if (hourSelect && hourSelect.options.length === 0) {
            for (let h = 1; h <= 12; h++) {
                const opt = document.createElement('option');
                opt.value = String(h).padStart(2, '0');
                opt.textContent = String(h).padStart(2, '0');
                hourSelect.appendChild(opt);
            }
        }
        if (minuteSelect && minuteSelect.options.length === 0) {
            for (let m = 0; m < 60; m += 5) {
                const opt = document.createElement('option');
                opt.value = String(m).padStart(2, '0');
                opt.textContent = String(m).padStart(2, '0');
                minuteSelect.appendChild(opt);
            }
        }
        if (periodSelect && periodSelect.options.length === 0) {
            ['am', 'pm'].forEach(p => {
                const opt = document.createElement('option');
                opt.value = p;
                opt.textContent = p.toUpperCase();
                periodSelect.appendChild(opt);
            });
        }
    },

    /**
     * Update daily reset time based on the select inputs
     * @param {boolean} forceUpdate - If true, bypass initialization check (for manual save button)
     */
    async updateResetTimeFromSelects(forceUpdate = false) {
        console.log('[DEBUG] updateResetTimeFromSelects called, _initializing:', this._initializing, 'forceUpdate:', forceUpdate);
        if (this._initializing && !forceUpdate) {
            console.log('[DEBUG] Blocked by _initializing flag');
            return; // Don't save while initializing
        }
        const hourSelect = document.getElementById('reset-hour-select');
        const minuteSelect = document.getElementById('reset-minute-select');
        const periodSelect = document.getElementById('reset-period-select');
        console.log('[DEBUG] Got selects:', { hourSelect: !!hourSelect, minuteSelect: !!minuteSelect, periodSelect: !!periodSelect });
        if (!hourSelect || !minuteSelect || !periodSelect) {
            console.log('[DEBUG] Missing select elements');
            return;
        }

        const hour12 = parseInt(hourSelect.value, 10);
        const period = periodSelect.value;
        const hour24 = this.convert12to24(hour12, period);
        const resetTime = `${String(hour24).padStart(2, '0')}:${minuteSelect.value}`;
        console.log('[DEBUG] Computed resetTime:', resetTime, { hour12, period, hour24, minute: minuteSelect.value });

        const prevTimeStr = (this._getCurrentSettings().daily_reset_time || '06:00');
        let prevHourVal = hourSelect.value;
        let prevMinuteVal = minuteSelect.value;
        let prevPeriodVal = periodSelect.value;
        try {
            const [h24Prev, mPrev] = String(prevTimeStr).split(':').map(Number);
            const converted = Settings.convert24to12(h24Prev);
            prevHourVal = String(converted.hour12).padStart(2, '0');
            prevMinuteVal = String(mPrev).padStart(2, '0');
            prevPeriodVal = converted.period;
        } catch (e) { /* no-op */ }
        
        try {
            console.log('[DEBUG] About to update daily_reset_time:', { daily_reset_time: resetTime });
            const updated = await this._putSettings({ daily_reset_time: resetTime });
            this._setCurrentSettings(updated);
            console.log('[DEBUG] Settings updated in AppState');
            if (typeof showNotification === 'function') {
                showNotification(`Daily reset time updated to ${resetTime}`, 'success');
            }
            window.incrementSettingsChangeCount?.();
            if (typeof window.setupDailyReset === 'function') {
                window.setupDailyReset();
            }
        } catch (error) {
            console.error('[DEBUG] Error in updateResetTimeFromSelects:', error);
            Utils.Logger.error('Error updating reset time:', error);
            try {
                hourSelect.value = prevHourVal;
                minuteSelect.value = prevMinuteVal;
                periodSelect.value = prevPeriodVal;
            } catch (e) { /* no-op */ }
            if (typeof showNotification === 'function') {
                showNotification('Error updating reset time', 'error');
            }
        }
    },

    /**
     * Debounced save for select-based time inputs
     */
    debouncedUpdateResetTimeFromSelects: function() {
        console.log('[DEBUG] debouncedUpdateResetTimeFromSelects called, _initializing:', Settings._initializing);
        if (Settings._initializing) {
            console.log('[DEBUG] Blocked by _initializing in debounced function');
            return; // Guard during init
        }
        if (window._resetTimeTimeout) {
            clearTimeout(window._resetTimeTimeout);
        }
        window._resetTimeTimeout = setTimeout(() => {
            console.log('[DEBUG] Debounce timeout fired, calling updateResetTimeFromSelects');
            Settings.updateResetTimeFromSelects();
            window._resetTimeTimeout = null;
        }, 1500);
    },

    /**
     * Update daily reset time using spinner controls
     */
    async updateResetTime() {
        const hourInput = document.getElementById('reset-hour');
        const minuteInput = document.getElementById('reset-minute');
        const amBtn = document.getElementById('period-am');
        const hiddenInput = document.getElementById('daily-reset-time');
        
        if (!hourInput || !minuteInput) return;
        
        // Get 12-hour format values
        const hour12 = parseInt(hourInput.value, 10);
        const minute = minuteInput.value.padStart(2, '0');
        const period = amBtn && amBtn.classList.contains('active') ? 'am' : 'pm';
        
        // Convert to 24-hour format for storage
        const hour24 = this.convert12to24(hour12, period);
        const resetTime = `${hour24.toString().padStart(2, '0')}:${minute}`;

        const prevTimeStr = (this._getCurrentSettings().daily_reset_time || (hiddenInput ? hiddenInput.value : '06:00') || '06:00');

        try {
            const updated = await this._putSettings({ daily_reset_time: resetTime });
            this._setCurrentSettings(updated);
            if (hiddenInput) hiddenInput.value = resetTime;
            
            // Show friendly 12-hour format in notification
            const displayTime = `${hour12.toString().padStart(2, '0')}:${minute} ${period.toUpperCase()}`;
            if (typeof showNotification === 'function') {
                showNotification(`Daily reset time updated to ${displayTime}`, 'success');
            }
            window.incrementSettingsChangeCount?.();
            
            // Re-setup daily reset timer
            if (typeof window.setupDailyReset === 'function') {
                window.setupDailyReset();
            }
        } catch (error) {
            Utils.Logger.error('Error updating reset time:', error);
            if (hiddenInput) hiddenInput.value = prevTimeStr;
            if (typeof showNotification === 'function') {
                showNotification('Error updating reset time', 'error');
            }
        }
    },

    /**
     * Convert 24-hour time to 12-hour with AM/PM
     */
    convert24to12(hours24) {
        let hour12 = hours24 % 12;
        if (hour12 === 0) hour12 = 12;
        const period = hours24 >= 12 ? 'pm' : 'am';
        return { hour12, period };
    },

    /**
     * Convert 12-hour time to 24-hour
     */
    convert12to24(hour12, period) {
        let hours24 = parseInt(hour12, 10);
        if (period === 'pm' && hours24 !== 12) {
            hours24 += 12;
        } else if (period === 'am' && hours24 === 12) {
            hours24 = 0;
        }
        return hours24;
    },

    /**
     * Update AM/PM period buttons
     */
    updatePeriodButtons(activePeriod) {
        const amBtn = document.getElementById('period-am');
        const pmBtn = document.getElementById('period-pm');
        
        if (amBtn) {
            amBtn.classList.toggle('active', activePeriod === 'am');
        }
        if (pmBtn) {
            pmBtn.classList.toggle('active', activePeriod === 'pm');
        }
    },

    /**
     * Adjust time spinner value (12-hour format)
     */
    adjustTime(inputId, direction) {
        const input = document.getElementById(inputId);
        if (!input) return;
        
        let value = parseInt(input.value, 10);
        
        if (inputId === 'reset-hour') {
            // Hours: 1-12 in 12-hour format
            value = value + direction;
            if (value > 12) value = 1;
            if (value < 1) value = 12;
        } else if (inputId === 'reset-minute') {
            // Minutes: 0-59
            value = (value + direction + 60) % 60;
        }
        
        input.value = String(value).padStart(2, '0');
        
        // Debounce the update - save after 2 seconds of no changes
        this.debouncedUpdateResetTime();
    },

    /**
     * Debounced save function - saves after 2 seconds of inactivity
     */
    debouncedUpdateResetTime: function() {
        // Clear previous timeout
        if (window._resetTimeTimeout) {
            clearTimeout(window._resetTimeTimeout);
        }
        
        // Set new timeout for 2 seconds
        window._resetTimeTimeout = setTimeout(() => {
            this.updateResetTime();
            window._resetTimeTimeout = null;
        }, 2000);
    }
};

// Export globally
window.Settings = Settings;

// Backward compatibility - expose methods as global functions
window.loadSettings = () => Settings.load();
window.updateAutostart = () => Settings.updateAutostart();
window.updateQuickProjectFromTitle = () => Settings.updateQuickProjectFromTitle();
window.updateCasualDates = () => Settings.updateCasualDates();
window.updateStreakSkipWeekends = () => Settings.updateStreakSkipWeekends();
window.updateStreakCountNewTasks = () => Settings.updateStreakCountNewTasks();
window.updateStreakCountSettings = () => Settings.updateStreakCountSettings();
window.updateAutosaveInterval = () => Settings.updateAutosaveInterval();
window.updateMiniAnalyticsInterval = () => Settings.updateMiniAnalyticsInterval();
window.updateSettingsLayout = () => Settings.updateSettingsLayout();
window.applyThemeAndDPI = () => Settings.applyThemeAndDPI();
window.updateTheme = () => Settings.updateTheme();
window.updateFinish = () => Settings.updateFinish();
window.updateIntensity = () => Settings.updateIntensity();
window.updateDPI = () => Settings.updateDPI();
window.updateCompactMode = () => Settings.updateCompactMode();
window.updateResetTime = () => Settings.updateResetTime();
window.updatePerfDisableBlur = () => Settings.updatePerfDisableBlur();
window.updatePerfDisableShadows = () => Settings.updatePerfDisableShadows();
window.updatePerfDisableAnimations = () => Settings.updatePerfDisableAnimations();
window.updatePerfDisableGlow = () => Settings.updatePerfDisableGlow();
window.applyPerfMaxPreset = () => Settings.applyPerfMaxPreset();

// Initialize time select/spinner event handlers when DOM loads
(function initResetTimeBindings(){
    let bindAttempts = 0;
    const MAX_BIND_ATTEMPTS = 5;
    
    function bind() {
        bindAttempts++;
        console.log(`[DEBUG] initResetTimeBindings bind() called (attempt ${bindAttempts})`);
        
        try { Settings.ensureTimeSelectOptions(); } catch(e) { console.error('[DEBUG] Error in ensureTimeSelectOptions:', e); }
        
        const hourSelect = document.getElementById('reset-hour-select');
        const minuteSelect = document.getElementById('reset-minute-select');
        const periodSelect = document.getElementById('reset-period-select');
        const saveBtn = document.getElementById('save-reset-time-btn');
        
        console.log('[DEBUG] Found elements:', { 
            hourSelect: !!hourSelect, 
            minuteSelect: !!minuteSelect, 
            periodSelect: !!periodSelect,
            saveBtn: !!saveBtn
        });
        
        // If elements not found and haven't exceeded max attempts, retry
        if ((!hourSelect || !minuteSelect || !periodSelect || !saveBtn) && bindAttempts < MAX_BIND_ATTEMPTS) {
            console.log(`[DEBUG] Elements not ready, retrying in 200ms...`);
            setTimeout(bind, 200);
            return;
        }
        
        const handler = () => {
            console.log('[DEBUG] Select change handler fired');
            try {
                if (saveBtn) {
                    saveBtn.disabled = false;
                    if (saveBtn.textContent && saveBtn.textContent !== 'Save') {
                        saveBtn.textContent = 'Save';
                    }
                }
            } catch (e) {}
        };
        
        if (hourSelect && !hourSelect._resetBound) {
            console.log('[DEBUG] Binding hourSelect');
            hourSelect.addEventListener('change', handler);
            hourSelect.addEventListener('input', handler);
            hourSelect._resetBound = true;
        }
        if (minuteSelect && !minuteSelect._resetBound) {
            console.log('[DEBUG] Binding minuteSelect');
            minuteSelect.addEventListener('change', handler);
            minuteSelect.addEventListener('input', handler);
            minuteSelect._resetBound = true;
        }
        if (periodSelect && !periodSelect._resetBound) {
            console.log('[DEBUG] Binding periodSelect');
            periodSelect.addEventListener('change', handler);
            periodSelect.addEventListener('input', handler);
            periodSelect._resetBound = true;
        }
        
        // Explicit save button - immediate save, no debounce
        if (saveBtn && !saveBtn._resetBound) {
            console.log('[DEBUG] Setting up save button');
            // Remove any existing onclick
            saveBtn.onclick = null;
            
            const clickHandler = async function(e) {
                console.log('[DEBUG] *** SAVE BUTTON CLICKED ***');
                e.preventDefault();
                e.stopPropagation();
                
                const originalText = saveBtn.textContent;
                try {
                    saveBtn.disabled = true;
                    saveBtn.textContent = 'Saving…';
                    console.log('[DEBUG] About to call updateResetTimeFromSelects directly with forceUpdate=true');
                    // Pass forceUpdate=true to bypass initialization check
                    await Settings.updateResetTimeFromSelects(true);
                    console.log('[DEBUG] updateResetTimeFromSelects completed successfully');
                    saveBtn.textContent = 'Saved!';
                    setTimeout(() => { 
                        saveBtn.textContent = 'Save';
                        saveBtn.disabled = false;
                    }, 1500);
                } catch (err) {
                    console.error('[DEBUG] Error in save button handler:', err);
                    saveBtn.textContent = 'Error';
                    setTimeout(() => { 
                        saveBtn.textContent = 'Save';
                        saveBtn.disabled = false;
                    }, 2000);
                }
            };
            
            // Bind directly
            saveBtn.addEventListener('click', clickHandler, false);
            saveBtn._resetBound = true;
            console.log('[DEBUG] Save button click handler bound successfully');
        }
        
        console.log('[DEBUG] Binding complete!');
    }
    
    // Expose bind function globally for re-binding after settings load
    window._bindResetTimeHandlers = bind;
    
    console.log('[DEBUG] Document readyState:', document.readyState);
    if (document.readyState !== 'loading') {
        console.log('[DEBUG] Calling bind() immediately');
        setTimeout(bind, 50); // Small delay to ensure DOM is fully ready
    } else {
        console.log('[DEBUG] Waiting for DOMContentLoaded');
        document.addEventListener('DOMContentLoaded', () => {
            console.log('[DEBUG] DOMContentLoaded fired, calling bind()');
            setTimeout(bind, 50);
        }, { once: true });
    }
})();

// ─── Triggers section ────────────────────────────────────────────────────────

/**
 * Generic helper: run a trigger button click, showing feedback on the button.
 * @param {string} btnId  - element id
 * @param {Function} action - async function to call
 */
async function _runTrigger(btnId, action) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    const original = btn.innerHTML;
    try {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running…';
        await action();
        btn.innerHTML = '<i class="fas fa-check"></i> Done!';
        setTimeout(() => { btn.innerHTML = original; btn.disabled = false; }, 2000);
    } catch (e) {
        btn.innerHTML = '<i class="fas fa-times"></i> Error';
        setTimeout(() => { btn.innerHTML = original; btn.disabled = false; }, 2500);
        console.error('[Triggers]', btnId, e);
    }
}

window.bindTriggerButtons = function bindTriggerButtons() {
    // Daily Reset
    const resetBtn = document.getElementById('trigger-daily-reset-btn');
    if (resetBtn && !resetBtn._triggerBound) {
        resetBtn._triggerBound = true;
        resetBtn.addEventListener('click', () => _runTrigger('trigger-daily-reset-btn', async () => {
            const caller = (typeof window.apiCall === 'function') ? window.apiCall
                : (url, opts) => fetch(url, Object.assign({ credentials: 'include' }, opts));
            const resp = await caller('/api/tasks/reset-daily-strikes', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            if (window.Utils && typeof window.Utils.safeShowNotification === 'function') {
                window.Utils.safeShowNotification('Daily reset triggered', 'success');
            }
        }));
    }

    // Planner Cleanup
    const cleanupBtn = document.getElementById('trigger-planner-cleanup-btn');
    if (cleanupBtn && !cleanupBtn._triggerBound) {
        cleanupBtn._triggerBound = true;
        cleanupBtn.addEventListener('click', () => _runTrigger('trigger-planner-cleanup-btn', async () => {
            const caller = (typeof window.apiCall === 'function') ? window.apiCall
                : (url, opts) => fetch(url, Object.assign({ credentials: 'include' }, opts));
            const resp = await caller('/api/planner-v2/cleanup-overdue', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json().catch(() => ({}));
            const n = data.unscheduled || 0;
            if (window.Utils && typeof window.Utils.safeShowNotification === 'function') {
                window.Utils.safeShowNotification(`Planner cleanup done — ${n} task${n !== 1 ? 's' : ''} unscheduled`, 'success');
            }
        }));
    }

    // Save Settings
    const saveSettingsBtn = document.getElementById('trigger-save-settings-btn');
    if (saveSettingsBtn && !saveSettingsBtn._triggerBound) {
        saveSettingsBtn._triggerBound = true;
        saveSettingsBtn.addEventListener('click', () => _runTrigger('trigger-save-settings-btn', async () => {
            if (window.Settings && typeof window.Settings._getCurrentSettings === 'function' && typeof window.Settings._putSettings === 'function') {
                await window.Settings._putSettings(window.Settings._getCurrentSettings());
            } else {
                throw new Error('Settings not ready');
            }
            if (window.Utils && typeof window.Utils.safeShowNotification === 'function') {
                window.Utils.safeShowNotification('Settings saved', 'success');
            }
        }));
    }
};

document.addEventListener('DOMContentLoaded', () => {
    try { window.bindTriggerButtons(); } catch (e) {}
});

// Daily recap manual trigger from Settings
window.bindShowRecapButton = function bindShowRecapButton() {
    if (!window.__recapDelegateBound) {
        window.__recapDelegateBound = true;
        document.addEventListener('click', async (e) => {
            try {
                const target = e.target && (e.target.closest ? e.target.closest('#show-recap-btn') : null);
                if (!target) return;
                e.preventDefault();
                if (window.AnalyticsExtras && window.AnalyticsExtras.DailyRecap && typeof window.AnalyticsExtras.DailyRecap.showNow === 'function') {
                    await window.AnalyticsExtras.DailyRecap.showNow();
                }
            } catch (err) { /* no-op */ }
        });
    }
};

document.addEventListener('DOMContentLoaded', () => {
    try { window.bindShowRecapButton(); } catch (e) {}
});

// Global explicit save function used by the Save button as a hard fallback
window.saveResetTimeNow = async function() {
    console.log('[DEBUG] saveResetTimeNow called (global fallback)');
    try {
        const hourSelect = document.getElementById('reset-hour-select');
        const minuteSelect = document.getElementById('reset-minute-select');
        const periodSelect = document.getElementById('reset-period-select');
        console.log('[DEBUG] Got selects in fallback:', { hourSelect: !!hourSelect, minuteSelect: !!minuteSelect, periodSelect: !!periodSelect });
        if (!hourSelect || !minuteSelect || !periodSelect) {
            try { Utils.safeShowNotification('Reset time controls not ready', 'error'); } catch(_) {}
            return;
        }
        var hour12 = parseInt(hourSelect.value, 10);
        var period = periodSelect.value === 'pm' ? 'pm' : 'am';
        var h24 = Settings.convert12to24(hour12, period);
        var resetTime = (String(h24).padStart(2, '0')) + ':' + minuteSelect.value;
        console.log('[DEBUG] Computed resetTime in fallback:', resetTime);

        try {
            if (window.Settings && typeof window.Settings._putSettings === 'function') {
                const updated = await window.Settings._putSettings({ daily_reset_time: resetTime });
                try { if (window.Settings._setCurrentSettings) window.Settings._setCurrentSettings(updated); } catch (e) {}
                console.log('[DEBUG] Fallback _putSettings succeeded');
            } else {
                // Prefer global apiCall if available; otherwise, fallback to fetch
                var caller = (typeof window.apiCall === 'function')
                    ? window.apiCall
                    : function(url, options) { return fetch(url, Object.assign({ credentials: 'include' }, options)); };
                console.log('[DEBUG] Using caller:', typeof window.apiCall === 'function' ? 'apiCall' : 'fetch');

                const resp = await caller('/api/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ daily_reset_time: resetTime })
                });
                console.log('[DEBUG] Fallback response:', { ok: resp && resp.ok, status: resp && resp.status });

                if (!(resp && resp.ok)) {
                    throw new Error('Failed to save reset time');
                }
            }

            try { Utils.safeShowNotification('Daily reset time updated to ' + resetTime, 'success'); } catch(_) {}
            try { if (typeof window.setupDailyReset === 'function') window.setupDailyReset(); } catch(_) {}
        } catch (e) {
            try { Utils.safeShowNotification('Failed to save reset time', 'error'); } catch(_) {}
        }
    } catch (e) {
        console.error('[DEBUG] Error in saveResetTimeNow:', e);
        try { Utils.safeShowNotification('Failed to save reset time', 'error'); } catch(_) {}
    }
};
