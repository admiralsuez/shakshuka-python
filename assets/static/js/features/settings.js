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
    /**
     * Load settings from server and apply them
     */
    async load() {
        // Guard to prevent change handlers from saving defaults during init
        this._initializing = true;
        try {
            const response = await apiCall('/api/settings');
            const settings = await response.json();
            AppState.set('currentSettings', settings);
            
            // Update UI elements
            const autostartToggle = document.getElementById('autostart-toggle');
            const autosaveInterval = document.getElementById('autosave-interval');
            const themeSelector = document.getElementById('theme-selector');
            const finishSelector = document.getElementById('finish-selector');
            const intensitySelector = document.getElementById('intensity-selector');
            const dpiSelector = document.getElementById('dpi-selector');
            const quickProjectToggle = document.getElementById('quick-project-from-title');
            const casualDatesToggle = document.getElementById('casual-dates-toggle');
            const hourSelect = document.getElementById('reset-hour-select');
            const minuteSelect = document.getElementById('reset-minute-select');
            const periodSelect = document.getElementById('reset-period-select');
            
            // Backend returns autostart_enabled; keep legacy "autostart" fallback just in case
            if (autostartToggle) {
                autostartToggle.checked = (typeof settings.autostart_enabled === 'boolean')
                    ? settings.autostart_enabled
                    : (settings.autostart || false);
            }
            if (autosaveInterval) autosaveInterval.value = settings.autosave_interval || 30;
            if (themeSelector) themeSelector.value = settings.theme || 'light';
            if (finishSelector) finishSelector.value = settings.finish || 'glossy';
            if (intensitySelector) intensitySelector.value = settings.intensity || '5';
            if (dpiSelector) dpiSelector.value = settings.dpi_scale || 100;
            if (quickProjectToggle) quickProjectToggle.checked = !!settings.quick_project_from_title;
            if (casualDatesToggle) casualDatesToggle.checked = !!settings.casual_dates;

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

    /**
     * Update autostart setting
     */
    async updateAutostart() {
        const enabled = document.getElementById('autostart-toggle').checked;
        
        try {
            const response = await apiCall('/api/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ autostart: enabled })
            });

            if (response.ok) {
                if (typeof showNotification === 'function') {
                    showNotification(
                        enabled ? 'Autostart enabled' : 'Autostart disabled', 
                        'success'
                    );
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update autostart setting');
            }
        } catch (error) {
            Utils.Logger.error('Error updating autostart:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating autostart setting', 'error');
            }
        }
    },

    /**
     * Update quick project-from-title toggle
     */
    async updateQuickProjectFromTitle() {
        const enabled = !!document.getElementById('quick-project-from-title')?.checked;
        
        try {
            const response = await apiCall('/api/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ quick_project_from_title: enabled })
            });

            if (response.ok) {
                const settings = AppState.get('currentSettings') || {};
                settings.quick_project_from_title = enabled;
                AppState.set('currentSettings', settings);
                if (typeof showNotification === 'function') {
                    showNotification(
                        enabled
                            ? 'Quick project from title enabled (first word before comma)'
                            : 'Quick project from title disabled',
                        'success'
                    );
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update quick project setting');
            }
        } catch (error) {
            Utils.Logger.error('Error updating quick project-from-title setting:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating quick project setting', 'error');
            }
        }
    },

    /**
     * Update casual dates toggle
     */
    async updateCasualDates() {
        const enabled = !!document.getElementById('casual-dates-toggle')?.checked;

        try {
            const response = await apiCall('/api/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ casual_dates: enabled })
            });

            if (response.ok) {
                const settings = AppState.get('currentSettings') || {};
                settings.casual_dates = enabled;
                AppState.set('currentSettings', settings);
                if (typeof showNotification === 'function') {
                    showNotification(
                        enabled
                            ? 'Casual dates enabled (today, in 2 days, this weekend)'
                            : 'Casual dates disabled',
                        'success'
                    );
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update casual date setting');
            }
        } catch (error) {
            Utils.Logger.error('Error updating casual dates setting:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating casual date setting', 'error');
            }
        }
    },

    /**
     * Update autosave interval setting
     */
    async updateAutosaveInterval() {
        const interval = parseInt(document.getElementById('autosave-interval').value);
        
        try {
            const response = await apiCall('/api/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ autosave_interval: interval })
            });

            if (response.ok) {
                if (typeof showNotification === 'function') {
                    showNotification('Auto-save interval updated', 'success');
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update autosave interval');
            }
        } catch (error) {
            Utils.Logger.error('Error updating autosave interval:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating auto-save interval', 'error');
            }
        }
    },

    /**
     * Apply theme and DPI settings to the page
     */
    applyThemeAndDPI() {
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
        
        // Apply additional CSS custom properties
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
        
        // Set CSS custom properties on both root and body
        Object.entries(additionalProperties).forEach(([property, value]) => {
            root.style.setProperty(`--${property}`, value);
            body.style.setProperty(`--${property}`, value);
        });
    },

    /**
     * Update theme setting
     */
    async updateTheme() {
        const theme = document.getElementById('theme-selector').value;
        
        try {
            const response = await apiCall('/api/settings', {
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
                this.applyThemeAndDPI();
                if (typeof showNotification === 'function') {
                    showNotification('Theme updated', 'success');
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update theme');
            }
        } catch (error) {
            Utils.Logger.error('Error updating theme:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating theme', 'error');
            }
        }
    },

    /**
     * Update finish setting
     */
    async updateFinish() {
        const finish = document.getElementById('finish-selector').value;
        
        try {
            const response = await apiCall('/api/settings', {
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
                this.applyThemeAndDPI();
                if (typeof showNotification === 'function') {
                    showNotification('Finish updated', 'success');
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update finish');
            }
        } catch (error) {
            Utils.Logger.error('Error updating finish:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating finish', 'error');
            }
        }
    },

    /**
     * Update intensity setting
     */
    async updateIntensity() {
        const intensity = document.getElementById('intensity-selector').value;
        
        try {
            const response = await apiCall('/api/settings', {
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
                this.applyThemeAndDPI();
                if (typeof showNotification === 'function') {
                    showNotification('Intensity updated', 'success');
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update intensity');
            }
        } catch (error) {
            Utils.Logger.error('Error updating intensity:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating intensity', 'error');
            }
        }
    },

    /**
     * Update DPI scale setting
     */
    async updateDPI() {
        const dpiScale = parseInt(document.getElementById('dpi-selector').value);
        
        try {
            const response = await apiCall('/api/settings', {
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
                this.applyThemeAndDPI();
                if (typeof showNotification === 'function') {
                    showNotification('DPI scale updated', 'success');
                }
                window.incrementSettingsChangeCount?.();
            } else {
                throw new Error('Failed to update DPI scale');
            }
        } catch (error) {
            Utils.Logger.error('Error updating DPI scale:', error);
            if (typeof showNotification === 'function') {
                showNotification('Error updating DPI scale', 'error');
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
        
        try {
            console.log('[DEBUG] About to call apiCall with:', { daily_reset_time: resetTime });
            const response = await apiCall('/api/settings', {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ daily_reset_time: resetTime })
            });
            console.log('[DEBUG] apiCall response:', { ok: response.ok, status: response.status });

            if (response.ok) {
                const settings = AppState.get('currentSettings') || {};
                settings.daily_reset_time = resetTime;
                AppState.set('currentSettings', settings);
                console.log('[DEBUG] Settings updated in AppState');
                if (typeof showNotification === 'function') {
                    showNotification(`Daily reset time updated to ${resetTime}`, 'success');
                }
                window.incrementSettingsChangeCount?.();
                if (typeof window.setupDailyReset === 'function') {
                    window.setupDailyReset();
                }
            } else {
                throw new Error('Failed to update reset time');
            }
        } catch (error) {
            console.error('[DEBUG] Error in updateResetTimeFromSelects:', error);
            Utils.Logger.error('Error updating reset time:', error);
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
        
        try {
            const response = await apiCall('/api/settings', {
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
            } else {
                throw new Error('Failed to update reset time');
            }
        } catch (error) {
            Utils.Logger.error('Error updating reset time:', error);
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
window.updateAutosaveInterval = () => Settings.updateAutosaveInterval();
window.applyThemeAndDPI = () => Settings.applyThemeAndDPI();
window.updateTheme = () => Settings.updateTheme();
window.updateFinish = () => Settings.updateFinish();
window.updateIntensity = () => Settings.updateIntensity();
window.updateDPI = () => Settings.updateDPI();
window.updateResetTime = () => Settings.updateResetTime();

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

        if (resp && resp.ok) {
            try {
                var settings = AppState.get ? (AppState.get('currentSettings') || {}) : {};
                settings.daily_reset_time = resetTime;
                if (AppState.set) AppState.set('currentSettings', settings);
            } catch (e) {}
            try { Utils.safeShowNotification('Daily reset time updated to ' + resetTime, 'success'); } catch(_) {}
            try { if (typeof window.setupDailyReset === 'function') window.setupDailyReset(); } catch(_) {}
        } else {
            try { Utils.safeShowNotification('Failed to save reset time', 'error'); } catch(_) {}
        }
    } catch (e) {
        console.error('[DEBUG] Error in saveResetTimeNow:', e);
        try { Utils.safeShowNotification('Failed to save reset time', 'error'); } catch(_) {}
    }
};
