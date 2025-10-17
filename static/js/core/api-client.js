/**
 * API Client - Handles all API communications
 * Centralized API management with CSRF token support
 */

// Global CSRF token cache
let csrfToken = null;

// Helper function to get CSRF token
async function getCSRFToken() {
    if (!csrfToken) {
        try {
            const response = await fetch('/api/csrf-token');
            const data = await response.json();
            csrfToken = data.csrf_token;
        } catch (error) {
            console.error('Failed to get CSRF token:', error);
            csrfToken = null;
        }
    }
    return csrfToken;
}

// Helper function to make authenticated requests with CSRF token
async function makeAuthenticatedRequest(url, options = {}) {
    const token = await getCSRFToken();
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            ...(token && { 'X-CSRF-Token': token })
        }
    };
    
    return fetch(url, { ...defaultOptions, ...options });
}

// API Error class for better error handling
class APIError extends Error {
    constructor(message, status, code) {
        super(message);
        this.status = status;
        this.code = code;
        this.name = 'APIError';
    }
}

// Generic API request handler with error handling
async function apiRequest(url, options = {}) {
    try {
        const response = await makeAuthenticatedRequest(url, options);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new APIError(
                errorData.error || `Request failed with status ${response.status}`,
                response.status,
                errorData.code
            );
        }
        
        return await response.json();
    } catch (error) {
        if (error instanceof APIError) {
            throw error;
        }
        throw new APIError(error.message || 'Network error', 0, 'NETWORK_ERROR');
    }
}

// Task API methods
const TaskAPI = {
    async getAll() {
        return await apiRequest('/api/tasks');
    },
    
    async create(taskData) {
        return await apiRequest('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
    },
    
    async update(taskId, taskData) {
        return await apiRequest(`/api/tasks/${taskId}`, {
            method: 'PUT',
            body: JSON.stringify(taskData)
        });
    },
    
    async delete(taskId) {
        return await apiRequest(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
    },
    
    async complete(taskId) {
        return await apiRequest(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });
    },
    
    async strike(taskId, strikeData) {
        return await apiRequest(`/api/tasks/${taskId}/strike`, {
            method: 'POST',
            body: JSON.stringify(strikeData)
        });
    }
};

// Settings API methods
const SettingsAPI = {
    async get() {
        return await apiRequest('/api/settings');
    },
    
    async update(settings) {
        return await apiRequest('/api/settings', {
            method: 'PUT',
            body: JSON.stringify(settings)
        });
    }
};

// Export for use in other modules
export { TaskAPI, SettingsAPI, APIError, apiRequest };
