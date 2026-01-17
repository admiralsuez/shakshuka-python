// Utility Functions Module

// Helper function to make authenticated requests with CSRF token
async function makeAuthenticatedRequest(url, options = {}) {
    const defaultHeaders = {
        'Content-Type': 'application/json'
    };

    // Include session cookie when auth is enabled
    let fetchOptions = { ...options, headers: { ...defaultHeaders, ...(options.headers || {}) } };

    if (window.APP_CONFIG && window.APP_CONFIG.authEnabled === true) {
        fetchOptions = {
            ...fetchOptions,
            credentials: 'include'
        };
    }

    return fetch(url, fetchOptions);
}

function _sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function _isPlainObject(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function _normalizeHeaders(headers) {
    const out = {};
    try {
        if (headers && typeof headers === 'object') {
            Object.keys(headers).forEach(k => {
                out[k] = headers[k];
            });
        }
    } catch (e) {
        return {};
    }
    return out;
}

function _hasHeader(headers, name) {
    const target = String(name || '').toLowerCase();
    return Object.keys(headers || {}).some(k => String(k).toLowerCase() === target);
}

async function apiCall(url, options = {}) {
    const headers = _normalizeHeaders(options.headers);
    if (!(options.body instanceof FormData) && !_hasHeader(headers, 'content-type')) {
        headers['Content-Type'] = 'application/json';
    }

    const timeoutMs = (typeof options.timeoutMs === 'number' && options.timeoutMs > 0) ? options.timeoutMs : 15000;
    const controller = new AbortController();
    const timer = setTimeout(() => {
        try { controller.abort(); } catch (e) { /* no-op */ }
    }, timeoutMs);

    try {
        return await fetch(url, {
            ...options,
            credentials: 'include',
            headers,
            signal: controller.signal
        });
    } finally {
        clearTimeout(timer);
    }
}

function _extractApiErrorMessage(status, data, fallbackText) {
    try {
        if (data && typeof data === 'object') {
            const msg = data.error || data.message;
            if (typeof msg === 'string' && msg.trim()) return msg;
        }
    } catch (e) { /* no-op */ }
    if (typeof fallbackText === 'string' && fallbackText.trim()) return fallbackText;
    return `HTTP ${status}`;
}

async function apiRequestJson(url, options = {}, config = {}) {
    const method = String(options.method || 'GET').toUpperCase();
    const isIdempotent = method === 'GET' || method === 'HEAD';
    const retries = (typeof config.retries === 'number') ? config.retries : (isIdempotent ? 1 : 0);
    const retryDelayMs = (typeof config.retryDelayMs === 'number' && config.retryDelayMs >= 0) ? config.retryDelayMs : 500;
    const validate = (typeof config.validate === 'function') ? config.validate : null;
    const expectObject = config.expectObject === true;
    const expectArray = config.expectArray === true;
    const expectSuccess = config.expectSuccess === true;

    let lastError = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const resp = await apiCall(url, options);
            const status = resp.status;

            const contentType = String(resp.headers.get('content-type') || '').toLowerCase();
            const likelyJson = contentType.includes('application/json') || contentType.includes('+json') || config.forceJson === true;

            let data = null;
            let text = '';

            if (status !== 204) {
                if (likelyJson) {
                    data = await resp.json().catch(() => null);
                } else {
                    text = await resp.text().catch(() => '');
                    data = null;
                }
            }

            if (!resp.ok) {
                const msg = _extractApiErrorMessage(status, data, text);
                const err = new Error(msg);
                err.status = status;
                err.data = data;
                err.url = url;

                if (attempt < retries && isIdempotent && (status === 408 || status === 429 || status === 502 || status === 503 || status === 504)) {
                    lastError = err;
                    await _sleep(retryDelayMs * (attempt + 1));
                    continue;
                }

                throw err;
            }

            if (expectObject && !_isPlainObject(data)) {
                const err = new Error('Invalid response shape (expected object)');
                err.status = status;
                err.data = data;
                err.url = url;
                throw err;
            }
            if (expectArray && !Array.isArray(data)) {
                const err = new Error('Invalid response shape (expected array)');
                err.status = status;
                err.data = data;
                err.url = url;
                throw err;
            }
            if (expectSuccess) {
                if (!_isPlainObject(data) || data.success !== true) {
                    const err = new Error(_extractApiErrorMessage(status, data, 'Operation failed'));
                    err.status = status;
                    err.data = data;
                    err.url = url;
                    throw err;
                }
            }
            if (validate) {
                const ok = validate(data);
                if (!ok) {
                    const err = new Error('Invalid response shape');
                    err.status = status;
                    err.data = data;
                    err.url = url;
                    throw err;
                }
            }

            return data;
        } catch (e) {
            lastError = e;
            const status = e && typeof e.status === 'number' ? e.status : null;
            if (attempt < retries && isIdempotent && (status == null || status === 408 || status === 429 || status === 502 || status === 503 || status === 504)) {
                await _sleep(retryDelayMs * (attempt + 1));
                continue;
            }
            throw e;
        }
    }

    throw lastError || new Error('Request failed');
}

async function apiRequestOk(url, options = {}, config = {}) {
    return await apiRequestJson(url, options, { ...config, expectSuccess: true, expectObject: true });
}

async function waitForHealthy(config = {}) {
    const timeoutMs = (typeof config.timeoutMs === 'number' && config.timeoutMs > 0) ? config.timeoutMs : 12000;
    const intervalMs = (typeof config.intervalMs === 'number' && config.intervalMs > 0) ? config.intervalMs : 250;
    const deadline = Date.now() + timeoutMs;
    let lastError = null;

    while (Date.now() < deadline) {
        try {
            const resp = await fetch('/health', { cache: 'no-store' });
            if (resp && resp.ok) return true;
        } catch (e) {
            lastError = e;
        }
        await _sleep(intervalMs);
    }

    try {
        if (lastError) Logger.warn('Backend health check timed out:', lastError);
    } catch (e) { }

    return false;
}

// Debug flag + helper (can be toggled via devtools if needed)
const DEBUG = false;
function debugLog(...args) {
    if (DEBUG) {
        console.log(...args);
    }
}

// Elements that are intentionally optional (loaded dynamically or page-specific)
const OPTIONAL_ELEMENTS = [
    // Quick actions - may not exist on all pages
    'quick-add-btn', 'focus-mode-btn', 'schedule-btn', 'sidebar-toggle',
    // Session management - disabled feature
    'reset-session-btn',
    // Settings elements - only exist on settings page
    'daily-reset-time', 'github-branch', 'update-channel', 'check-interval',
    // GitHub update modal - dynamically loaded
    'close-github-update-modal', 'cancel-github-update', 'download-github-update',
    // Import functionality - modal loaded on demand
    'import-tasks-btn', 'close-import-modal', 'cancel-import', 'confirm-import',
    'import-file', 'download-sample',
    // Password modal - feature removed
    'close-password-modal', 'cancel-password', 'save-password',
    // Planner-specific elements
    'add-task-to-planner', 'prev-day', 'next-day'
];

// Helper function to safely add event listeners
function safeAddEventListener(elementId, event, handler) {
    const element = document.getElementById(elementId);
    if (element) {
        element.addEventListener(event, handler);
    } else if (!OPTIONAL_ELEMENTS.includes(elementId) &&
               !elementId.includes('password') &&
               !elementId.includes('Password')) {
        // Only warn for unexpected missing elements
        console.debug(`Element '${elementId}' not found (may be loaded later)`);
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
        if (typeof AppState !== 'undefined' && AppState && AppState.get && AppState.get('developerLogs')) {
            AppState.get('developerLogs').push({
                type: 'error',
                message: event.error.message,
                stack: event.error.stack,
                timestamp: new Date().toLocaleString()
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
        if (typeof AppState !== 'undefined' && AppState && AppState.get && AppState.get('developerLogs')) {
            AppState.get('developerLogs').push({
                type: 'error',
                message: `Promise rejection: ${event.reason}`,
                stack: (event.reason && event.reason.stack) ? event.reason.stack : 'No stack trace',
                timestamp: new Date().toLocaleString()
            });
        }
    } catch (e) {
        console.error('Error logging promise rejection:', e);
    }
});

// Custom Logger (don't override console)
const Logger = {
    log: (message, type = 'info') => {
        const timestamp = new Date().toLocaleString();
        const logEntry = { type, message, timestamp };

        // Add to AppState developer logs if available
        try {
            if (typeof AppState !== 'undefined' && AppState && AppState.get && AppState.get('developerLogs')) {
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
    warn: (message) => Logger.log(message, 'warning'),
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
    } catch (e) {
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
    makeAuthenticatedRequest,
    apiCall,
    apiRequestJson,
    apiRequestOk,
    waitForHealthy,
    safeShowNotification,
    sanitizeHTML,
    formatDate,
    formatTime,
    debounce,
    throttle,
    generateId,
    deepClone,
    isElementVisible,
    getElementPosition,
    showLoading,
    hideLoading,
    isValidEmail,
    isValidUrl,
    formatFileSize,
    copyToClipboard,
    downloadFile,
    scrollToElement,
    Logger,
    safeAddEventListener,
    debugLog
};
