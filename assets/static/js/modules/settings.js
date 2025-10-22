/**
 * Settings Module - Handles application settings, themes, and preferences
 */

const Settings = (function() {
    'use strict';
    
    // ==================== Settings Management ====================
    
    async function loadSettings() {
        try {
            const response = await fetch('/api/settings');
            if (response.ok) {
                const settings = await response.json();
                applySettings(settings);
                return settings;
            }
        } catch (error) {
            console.error('Error loading settings:', error);
        }
        return null;
    }
    
    async function saveSettings(settings) {
        try {
            const response = await fetch('/api/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(settings)
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    UI.showSuccess('Settings saved successfully');
                    applySettings(settings);
                    return true;
                }
            }
            
            UI.showError('Failed to save settings');
            return false;
        } catch (error) {
            console.error('Error saving settings:', error);
            UI.showError('Error saving settings');
            return false;
        }
    }
    
    function applySettings(settings) {
        if (!settings) return;
        
        // Apply theme
        if (settings.theme) {
            applyTheme(settings.theme);
        }
        
        // Apply DPI
        if (settings.dpi) {
            applyDPI(settings.dpi);
        }
        
        // Apply autostart
        if (settings.autostart !== undefined) {
            updateAutostartUI(settings.autostart);
        }
        
        // Apply daily reset
        if (settings.dailyResetTime) {
            updateDailyResetUI(settings.dailyResetTime);
        }
    }
    
    // ==================== Theme Management ====================
    
    function applyTheme(theme) {
        document.body.className = document.body.className.replace(/theme-\w+/g, '');
        document.body.classList.add(`theme-${theme}`);
        
        // Update theme selector if on settings page
        const themeSelector = document.getElementById('theme-selector');
        if (themeSelector) {
            themeSelector.value = theme;
        }
        
        // Save to localStorage
        localStorage.setItem('theme', theme);
    }
    
    async function updateTheme(theme) {
        applyTheme(theme);
        
        // Save to server
        const settings = await loadSettings() || {};
        settings.theme = theme;
        await saveSettings(settings);
    }
    
    // ==================== DPI/Zoom Management ====================
    
    function applyDPI(dpi) {
        const root = document.documentElement;
        root.style.fontSize = `${dpi}px`;
        
        // Update DPI selector if on settings page
        const dpiSelector = document.getElementById('dpi-selector');
        if (dpiSelector) {
            dpiSelector.value = dpi;
        }
        
        // Save to localStorage
        localStorage.setItem('dpi', dpi);
    }
    
    async function updateDPI(dpi) {
        applyDPI(dpi);
        
        // Save to server
        const settings = await loadSettings() || {};
        settings.dpi = dpi;
        await saveSettings(settings);
    }
    
    // ==================== Autostart Management ====================
    
    function updateAutostartUI(enabled) {
        const autostartCheckbox = document.getElementById('autostart-checkbox');
        if (autostartCheckbox) {
            autostartCheckbox.checked = enabled;
        }
    }
    
    async function toggleAutostart(enabled) {
        try {
            const response = await fetch('/api/system/autostart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ enabled })
            });
            
            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    UI.showSuccess(`Autostart ${enabled ? 'enabled' : 'disabled'}`);
                    
                    // Update settings
                    const settings = await loadSettings() || {};
                    settings.autostart = enabled;
                    await saveSettings(settings);
                    
                    return true;
                }
            }
            
            UI.showError('Failed to update autostart');
            return false;
        } catch (error) {
            console.error('Error updating autostart:', error);
            UI.showError('Error updating autostart');
            return false;
        }
    }
    
    // ==================== Daily Reset Management ====================
    
    function updateDailyResetUI(time) {
        const resetTimeInput = document.getElementById('daily-reset-time');
        if (resetTimeInput) {
            resetTimeInput.value = time;
        }
    }
    
    async function updateDailyResetTime(time) {
        const settings = await loadSettings() || {};
        settings.dailyResetTime = time;
        return await saveSettings(settings);
    }
    
    // ==================== Settings Page Initialization ====================
    
    async function initializeSettingsPage() {
        const settings = await loadSettings();
        if (!settings) return;
        
        // Populate all settings fields
        const fields = {
            'theme-selector': settings.theme,
            'dpi-selector': settings.dpi,
            'autostart-checkbox': settings.autostart,
            'daily-reset-time': settings.dailyResetTime,
        };
        
        for (const [fieldId, value] of Object.entries(fields)) {
            const element = document.getElementById(fieldId);
            if (element) {
                if (element.type === 'checkbox') {
                    element.checked = value;
                } else {
                    element.value = value;
                }
            }
        }
    }
    
    // ==================== Public API ====================
    
    return {
        // Settings
        loadSettings,
        saveSettings,
        applySettings,
        initializeSettingsPage,
        
        // Theme
        applyTheme,
        updateTheme,
        
        // DPI
        applyDPI,
        updateDPI,
        
        // Autostart
        toggleAutostart,
        
        // Daily Reset
        updateDailyResetTime
    };
})();

// Expose to global scope
window.Settings = Settings;

