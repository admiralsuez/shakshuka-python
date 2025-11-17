/**
 * Error Handler Module
 * Provides global error handling and async function wrappers
 */

const ErrorHandler = (function() {
    'use strict';

    // Setup global error handlers
    function setupGlobalErrorHandlers() {
        // Uncaught errors
        window.addEventListener('error', function(event) {
            logError('Uncaught error', {
                message: event.message,
                filename: event.filename,
                line: event.lineno,
                column: event.colno,
                error: event.error
            });
            
            showUserFriendlyError('An unexpected error occurred. Please refresh the page.');
            
            // Prevent default browser error handling
            event.preventDefault();
        });

        // Unhandled promise rejections
        window.addEventListener('unhandledrejection', function(event) {
            logError('Unhandled promise rejection', {
                reason: event.reason,
                promise: event.promise
            });
            
            showUserFriendlyError('An operation failed. Please try again.');
            
            // Prevent default browser error handling
            event.preventDefault();
        });
    }

    // Wrapper for async functions with automatic error handling
    async function safeAsync(fn, errorMessage = 'Operation failed') {
        try {
            return await fn();
        } catch (error) {
            logError(errorMessage, error);
            showUserFriendlyError(errorMessage);
            return null;
        }
    }

    // Wrapper for synchronous functions with automatic error handling
    function safeSyn(fn, errorMessage = 'Operation failed') {
        try {
            return fn();
        } catch (error) {
            logError(errorMessage, error);
            showUserFriendlyError(errorMessage);
            return null;
        }
    }

    // Log error with context
    function logError(message, error) {
        if (typeof Utils !== 'undefined' && Utils.Logger) {
            Utils.Logger.error(message, error);
        } else {
            console.error(message, error);
        }
    }

    // Show user-friendly error message
    function showUserFriendlyError(message) {
        if (typeof Utils !== 'undefined' && Utils.safeShowNotification) {
            Utils.safeShowNotification(message, 'error');
        } else if (typeof showNotification === 'function') {
            showNotification(message, 'error');
        }
    }

    // Retry failed async operations
    async function retryAsync(fn, retries = 3, delay = 1000) {
        for (let i = 0; i < retries; i++) {
            try {
                return await fn();
            } catch (error) {
                if (i === retries - 1) {
                    throw error;
                }
                logError(`Retry attempt ${i + 1} failed`, error);
                await new Promise(resolve => setTimeout(resolve, delay));
            }
        }
    }

    // Initialize error handling
    function init() {
        setupGlobalErrorHandlers();
        if (typeof Utils !== 'undefined' && Utils.Logger) {
            Utils.Logger.info('Error handlers initialized');
        } else {
            console.info('Error handlers initialized');
        }
    }

    // Public API
    return {
        init,
        safeAsync,
        safeSyn,
        retryAsync,
        logError,
        showUserFriendlyError
    };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function() {
        ErrorHandler.init();
    });
} else {
    ErrorHandler.init();
}
