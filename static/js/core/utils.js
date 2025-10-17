/**
 * Utility Functions
 * Common helper functions used throughout the application
 */

// Custom Logger (don't override console)
const Logger = {
    log: (...args) => {
        console.log(...args);
        addLog('info', args.join(' '));
    },
    error: (...args) => {
        console.error(...args);
        addLog('error', args.join(' '));
    },
    warn: (...args) => {
        console.warn(...args);
        addLog('warning', args.join(' '));
    },
    info: (...args) => {
        console.info(...args);
        addLog('info', args.join(' '));
    }
};

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
            console.log(`Notification (${type}): ${message}`);
        }
    } catch (error) {
        console.error('Error showing notification:', error);
        console.log(`Notification (${type}): ${message}`);
    }
}

// HTML escape function to prevent XSS
function escapeHtml(str) {
    if (!str) return '';
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}

// Debounce function for performance optimization
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Throttle function for performance optimization
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Format date for display
function formatDate(date) {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleDateString();
}

// Format time for display
function formatTime(date) {
    if (!date) return '';
    const d = new Date(date);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Generate unique ID
function generateId() {
    return Math.random().toString(36).substr(2, 9);
}

// Validate email format
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Validate URL format
function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

// Deep clone object
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (obj instanceof Array) return obj.map(item => deepClone(item));
    if (typeof obj === 'object') {
        const clonedObj = {};
        for (const key in obj) {
            if (obj.hasOwnProperty(key)) {
                clonedObj[key] = deepClone(obj[key]);
            }
        }
        return clonedObj;
    }
}

// Export for use in other modules
export {
    Logger,
    safeAddEventListener,
    safeShowNotification,
    escapeHtml,
    debounce,
    throttle,
    formatDate,
    formatTime,
    generateId,
    isValidEmail,
    isValidUrl,
    deepClone
};
