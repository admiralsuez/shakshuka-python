/**
 * Error Handler - Graceful degradation and error handling for critical operations
 */

class ErrorHandler {
    constructor() {
        this.errorLog = [];
        this.maxLogSize = 100;
    }

    /**
     * Wrap a critical operation with error handling and user feedback
     * @param {Function} operation - The async operation to execute
     * @param {Object} options - Configuration options
     * @returns {Promise} - Result or graceful fallback
     */
    async withGracefulDegradation(operation, options = {}) {
        const {
            operationName = 'Operation',
            fallbackValue = null,
            showErrorToUser = true,
            retryCount = 0,
            retryDelay = 1000,
            onError = null,
            onSuccess = null
        } = options;

        let lastError = null;
        
        for (let attempt = 0; attempt <= retryCount; attempt++) {
            try {
                const result = await operation();
                
                if (onSuccess) {
                    onSuccess(result);
                }
                
                return result;
            } catch (error) {
                lastError = error;
                console.error(`[ErrorHandler] ${operationName} failed (attempt ${attempt + 1}/${retryCount + 1}):`, error);
                
                // Log error
                this.logError(operationName, error);
                
                // Retry if attempts remaining
                if (attempt < retryCount) {
                    await this.delay(retryDelay);
                    continue;
                }
            }
        }
        
        // All attempts failed
        if (showErrorToUser && typeof showNotification === 'function') {
            showNotification(`${operationName} failed. ${lastError?.message || 'Please try again.'}`, 'error');
        }
        
        if (onError) {
            onError(lastError);
        }
        
        return fallbackValue;
    }

    /**
     * Wrap critical operations (save, delete, strike) with proper error handling
     */
    async criticalOperation(operation, options = {}) {
        const {
            operationName = 'Critical Operation',
            successMessage = null,
            onSuccess = null,
            onError = null
        } = options;

        try {
            const result = await operation();
            
            if (successMessage && typeof showNotification === 'function') {
                showNotification(successMessage, 'success');
            }
            
            if (onSuccess) {
                onSuccess(result);
            }
            
            return { success: true, data: result };
        } catch (error) {
            console.error(`[ErrorHandler] ${operationName} failed:`, error);
            this.logError(operationName, error);
            
            // Always show error for critical operations
            if (typeof showNotification === 'function') {
                const errorMsg = error.message || 'An unexpected error occurred';
                showNotification(`${operationName} failed: ${errorMsg}`, 'error');
            }
            
            if (onError) {
                onError(error);
            }
            
            return { success: false, error: error.message };
        }
    }

    /**
     * Fetch with graceful degradation
     */
    async fetchWithFallback(url, options = {}) {
        const {
            fallbackValue = null,
            cacheTTL = 0,
            cacheKey = url,
            showError = false
        } = options;

        const fetchOptions = { ...options };
        delete fetchOptions.fallbackValue;
        delete fetchOptions.cacheTTL;
        delete fetchOptions.cacheKey;
        delete fetchOptions.showError;

        // Check cache first
        if (cacheTTL > 0) {
            const cached = this.getFromCache(cacheKey);
            if (cached) {
                return cached;
            }
        }

        try {
            const response = await fetch(url, fetchOptions);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Cache if TTL specified
            if (cacheTTL > 0) {
                this.setCache(cacheKey, data, cacheTTL);
            }
            
            return data;
        } catch (error) {
            console.warn(`[ErrorHandler] Fetch failed for ${url}, using fallback:`, error);
            this.logError(`Fetch ${url}`, error);
            
            if (showError && typeof showNotification === 'function') {
                showNotification('Failed to load data. Using cached or default values.', 'warning');
            }
            
            return fallbackValue;
        }
    }

    /**
     * Simple cache implementation
     */
    cache = new Map();

    getFromCache(key) {
        const item = this.cache.get(key);
        if (!item) return null;
        
        if (Date.now() > item.expiry) {
            this.cache.delete(key);
            return null;
        }
        
        return item.data;
    }

    setCache(key, data, ttl) {
        this.cache.set(key, {
            data,
            expiry: Date.now() + ttl
        });
    }

    clearCache() {
        this.cache.clear();
    }

    /**
     * Log error to internal log
     */
    logError(operation, error) {
        this.errorLog.push({
            timestamp: new Date().toISOString(),
            operation,
            message: error.message,
            stack: error.stack
        });
        
        // Keep log size manageable
        if (this.errorLog.length > this.maxLogSize) {
            this.errorLog.shift();
        }
    }

    /**
     * Get recent errors
     */
    getRecentErrors(count = 10) {
        return this.errorLog.slice(-count);
    }

    /**
     * Delay helper
     */
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// Create global instance
window.ErrorHandler = new ErrorHandler();

// Export helper functions for convenience
window.withGracefulDegradation = (operation, options) => 
    window.ErrorHandler.withGracefulDegradation(operation, options);

window.criticalOperation = (operation, options) => 
    window.ErrorHandler.criticalOperation(operation, options);

window.fetchWithFallback = (url, options) => 
    window.ErrorHandler.fetchWithFallback(url, options);
