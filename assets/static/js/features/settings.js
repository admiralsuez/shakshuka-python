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
    /**
     * Load settings from server and apply them
     */
    async load() {
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
            const resetTimeInput = document.getElementById('daily-reset-time');
            
            if (autostartToggle) autostartToggle.checked = settings.autostart || false;
            if (autosaveInterval) autosaveInterval.value = settings.autosave_interval || 30;
            if (themeSelector) themeSelector.value = settings.theme || 'light';
            if (finishSelector) finishSelector.value = settings.finish || 'glossy';
            if (intensitySelector) intensitySelector.value = settings.intensity || '5';
            if (dpiSelector) dpiSelector.value = settings.dpi_scale || 100;
            if (resetTimeInput) resetTimeInput.value = settings.daily_reset_time || '08:00';
            
            this.applyThemeAndDPI();
            
            // Ensure daily reset timer uses latest settings
            if (typeof window.setupDailyReset === 'function') {
                window.setupDailyReset();
            }
            
            // Hide loading screen after settings are applied
            if (typeof hideLoadingScreen === 'function') {
                hideLoadingScreen();
            }
        } catch (error) {
            Utils.Logger.error('Error loading settings:', error);
            // Hide loading screen even if there's an error
            if (typeof hideLoadingScreen === 'function') {
                hideLoadingScreen();
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
    }
};

// Export globally
window.Settings = Settings;

// Backward compatibility - expose methods as global functions
window.loadSettings = () => Settings.load();
window.updateAutostart = () => Settings.updateAutostart();
window.updateAutosaveInterval = () => Settings.updateAutosaveInterval();
window.applyThemeAndDPI = () => Settings.applyThemeAndDPI();
window.updateTheme = () => Settings.updateTheme();
window.updateFinish = () => Settings.updateFinish();
window.updateIntensity = () => Settings.updateIntensity();
window.updateDPI = () => Settings.updateDPI();
