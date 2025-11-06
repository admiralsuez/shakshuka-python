/**
 * Shakshuka Application Initialization
 * Main entry point that coordinates all modules
 * Version: 2.3.0
 */

(function() {
    'use strict';

    // Loading screen management
    function hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const appContainer = document.getElementById('app-container');
        
        if (loadingScreen && appContainer) {
            loadingScreen.classList.add('fade-out');
            appContainer.style.display = 'block';
            
            setTimeout(() => {
                loadingScreen.style.display = 'none';
            }, 500);
        }
    }

    function showLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const appContainer = document.getElementById('app-container');
        
        if (loadingScreen && appContainer) {
            loadingScreen.style.display = 'flex';
            appContainer.style.display = 'none';
        }
    }

    // Initialize the application
    async function initializeApp() {
        try {
            // Wait for all scripts to load
            if (typeof Utils === 'undefined' || typeof Utils.Logger === 'undefined') {
                console.log('Waiting for Utils module...');
                setTimeout(initializeApp, 100);
                return;
            }
            
            Utils.Logger.info('Shakshuka application initializing...');
            
            // Show loading screen
            showLoadingScreen();

            // Check authentication status
            if (typeof Auth !== 'undefined' && typeof Auth.checkAuthStatus === 'function') {
                await Auth.checkAuthStatus();
            } else {
                Utils.Logger.warn('Auth module not available, skipping authentication check');
            }

            // Setup event listeners only once
            if (!window.eventListenersSetup) {
                if (typeof setupEventListeners === 'function') {
                    setupEventListeners();
                    Utils.Logger.info('Event listeners setup complete');
                } else {
                    Utils.Logger.warn('setupEventListeners not available yet');
                }
                window.eventListenersSetup = true;
            }

            // Setup keyboard shortcuts
            if (typeof Keyboard !== 'undefined' && typeof Keyboard.setup === 'function') {
                Keyboard.setup();
                Utils.Logger.info('Keyboard shortcuts initialized');
            } else {
                Utils.Logger.warn('Keyboard module not available, skipping keyboard shortcuts');
            }

            Utils.Logger.info('Shakshuka application initialized successfully');
            
        } catch (error) {
            // Log as warning since app usually recovers from this
            Utils.Logger.warn('Initialization encountered an error (app may continue):', error);
            console.warn('Initialization error details:', error.message, error.stack);
            // Don't show error to user since app usually works fine anyway
            // The error is typically non-fatal and app continues to function
        }
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeApp);
    } else {
        initializeApp();
    }

    // Export globally
    window.ShakshukaApp = {
        hideLoadingScreen,
        showLoadingScreen,
        initialize: initializeApp
    };
})();
