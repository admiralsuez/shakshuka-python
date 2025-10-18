// Utility Functions Module

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
    
    // Get user ID from AppState
    const userId = AppState.get('userId');
    console.log('User ID:', userId);

    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'X-CSRF-Token': token }),
            ...(userId && { 'X-User-ID': userId })
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

// Custom Logger (don't override console)
const Logger = {
    log: (message, type = 'info') => {
        const timestamp = new Date().toISOString();
        const logEntry = { type, message, timestamp };

        // Add to AppState developer logs if available
        try {
            if (AppState && AppState.get && AppState.get('developerLogs')) {
                const logs = AppState.get('developerLogs');
                logs.push(logEntry);

                // Keep only last 100 logs to prevent memory issues
                if (logs.length > 100) {
                    logs.splice(0, logs.length - 100);
                }
            }
        } catch (e) {
            console.error('Error adding to developer logs:', e);
        }

        // Console logging based on type
        switch (type) {
            case 'error':
                console.error(`[${timestamp}] ERROR:`, message);
                break;
            case 'warning':
                console.warn(`[${timestamp}] WARNING:`, message);
                break;
            case 'info':
                console.info(`[${timestamp}] INFO:`, message);
                break;
            case 'debug':
                console.debug(`[${timestamp}] DEBUG:`, message);
                break;
            default:
                console.log(`[${timestamp}]`, message);
        }
    },

    error: (message) => Logger.log(message, 'error'),
    warning: (message) => Logger.log(message, 'warning'),
    info: (message) => Logger.log(message, 'info'),
    debug: (message) => Logger.log(message, 'debug')
};

// XSS Protection - Sanitize HTML
function sanitizeHTML(str) {
    const temp = document.createElement('div');
    temp.textContent = str;
    return temp.innerHTML;
}

// Helper function to format dates
function formatDate(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });
}

// Helper function to format time
function formatTime(date) {
    if (!(date instanceof Date)) {
        date = new Date(date);
    }
    return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
}

// Helper function to debounce function calls
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

// Helper function to throttle function calls
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

// Helper function to generate unique IDs
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

// Helper function to deep clone objects
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') return obj;
    if (obj instanceof Date) return new Date(obj.getTime());
    if (Array.isArray(obj)) return obj.map(item => deepClone(item));

    const clonedObj = {};
    for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
            clonedObj[key] = deepClone(obj[key]);
        }
    }
    return clonedObj;
}

// Helper function to check if element is visible
function isElementVisible(element) {
    return element && element.offsetParent !== null;
}

// Helper function to get element position
function getElementPosition(element) {
    const rect = element.getBoundingClientRect();
    return {
        top: rect.top + window.pageYOffset,
        left: rect.left + window.pageXOffset,
        width: rect.width,
        height: rect.height
    };
}

// Helper function to animate element
function animateElement(element, keyframes, options = {}) {
    const defaultOptions = {
        duration: 300,
        easing: 'ease-in-out',
        fill: 'forwards'
    };

    return element.animate(keyframes, { ...defaultOptions, ...options });
}

// Helper function to show loading state
function showLoading(element, text = 'Loading...') {
    if (element) {
        element.innerHTML = `
            <div class="loading-spinner" style="display: inline-block; width: 16px; height: 16px; border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; animation: spin 1s linear infinite; margin-right: 8px;"></div>
            ${text}
        `;
        element.disabled = true;
    }
}

// Helper function to hide loading state
function hideLoading(element, originalText) {
    if (element) {
        element.innerHTML = originalText;
        element.disabled = false;
    }
}

// Helper function to validate email
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

// Helper function to validate URL
function isValidUrl(url) {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
}

// Helper function to format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Helper function to copy text to clipboard
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch (err) {
        console.error('Failed to copy text: ', err);
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            document.body.removeChild(textArea);
            return true;
        } catch (fallbackErr) {
            document.body.removeChild(textArea);
            return false;
        }
    }
}

// Helper function to download data as file
function downloadFile(data, filename, type = 'application/json') {
    const blob = new Blob([data], { type });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
}

// Helper function to read file as text
function readFileAsText(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e);
        reader.readAsText(file);
    });
}

// Helper function to read file as data URL
function readFileAsDataURL(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => resolve(e.target.result);
        reader.onerror = (e) => reject(e);
        reader.readAsDataURL(file);
    });
}

// Helper function to get query parameters
function getQueryParams() {
    const params = new URLSearchParams(window.location.search);
    const result = {};
    for (const [key, value] of params) {
        result[key] = value;
    }
    return result;
}

// Helper function to set query parameters
function setQueryParams(params) {
    const url = new URL(window.location);
    Object.keys(params).forEach(key => {
        if (params[key] !== null && params[key] !== undefined) {
            url.searchParams.set(key, params[key]);
        } else {
            url.searchParams.delete(key);
        }
    });
    window.history.pushState({}, '', url);
}

// Helper function to scroll to element
function scrollToElement(element, offset = 0) {
    if (element) {
        const elementPosition = element.offsetTop - offset;
        window.scrollTo({
            top: elementPosition,
            behavior: 'smooth'
        });
    }
}

// Helper function to check if element is in viewport
function isElementInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

// Helper function to get element siblings
function getSiblings(element) {
    const siblings = [];
    let sibling = element.parentNode.firstChild;

    while (sibling) {
        if (sibling.nodeType === 1 && sibling !== element) {
            siblings.push(sibling);
        }
        sibling = sibling.nextSibling;
    }

    return siblings;
}

// Helper function to add/remove classes with animation
function animateClassChange(element, className, action = 'add') {
    if (action === 'add') {
        element.classList.add(className);
    } else {
        element.classList.remove(className);
    }

    // Force reflow to ensure animation
    element.offsetHeight;

    return element;
}

// Helper function to wait for DOM ready
function ready(callback) {
    if (document.readyState !== 'loading') {
        callback();
    } else {
        document.addEventListener('DOMContentLoaded', callback);
    }
}

// Helper function to wait for element
function waitForElement(selector, callback, timeout = 5000) {
    const element = document.querySelector(selector);
    if (element) {
        callback(element);
        return;
    }

    const observer = new MutationObserver(() => {
        const element = document.querySelector(selector);
        if (element) {
            observer.disconnect();
            callback(element);
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Timeout fallback
    setTimeout(() => {
        observer.disconnect();
        const element = document.querySelector(selector);
        if (element) {
            callback(element);
        }
    }, timeout);
}

// Export functions for use in other modules
window.Utils = {
    getCSRFToken,
    makeAuthenticatedRequest,
    safeAddEventListener,
    safeShowNotification,
    Logger,
    sanitizeHTML,
    formatDate,
    formatTime,
    debounce,
    throttle,
    generateId,
    deepClone,
    isElementVisible,
    getElementPosition,
    animateElement,
    showLoading,
    hideLoading,
    isValidEmail,
    isValidUrl,
    formatFileSize,
    copyToClipboard,
    downloadFile,
    readFileAsText,
    readFileAsDataURL,
    getQueryParams,
    setQueryParams,
    scrollToElement,
    isElementInViewport,
    getSiblings,
    animateClassChange,
    ready,
    waitForElement
};
