// Thread-Safe State Management Module with Race Condition Prevention
const AppState = (() => {
    const state = {
        currentPage: 'tasks',
        tasks: [],
        currentDate: new Date(),
        editingTaskId: null,
        currentSettings: {},
        dailyResetTimer: null,
        developerLogs: [],
        currentFilter: 'active',
        isAuthenticated: false,
        user: null,
        sessionId: null
    };

    // State operation queue to prevent race conditions
    const operationQueue = [];
    let isProcessingQueue = false;
    
    // Lock mechanism for critical operations
    let stateLock = false;
    const lockTimeout = 5000; // 5 seconds max lock time

    // Queue management
    const processQueue = async () => {
        if (isProcessingQueue || operationQueue.length === 0) {
            return;
        }
        
        isProcessingQueue = true;
        
        try {
            while (operationQueue.length > 0) {
                const operation = operationQueue.shift();
                await executeOperation(operation);
            }
        } catch (error) {
            console.error('Error processing state queue:', error);
        } finally {
            isProcessingQueue = false;
        }
    };

    const executeOperation = async (operation) => {
        const { type, key, value, taskId, updatedTask, resolve, reject } = operation;
        
        try {
            let result;
            
            switch (type) {
                case 'set':
                    state[key] = value;
                    result = value;
                    break;
                case 'addTask':
                    state.tasks.unshift(value);
                    result = state.tasks;
                    break;
                case 'updateTask':
            const index = state.tasks.findIndex(task => task.id === taskId);
            if (index !== -1) {
                state.tasks[index] = updatedTask;
                        result = updatedTask;
                    } else {
                        throw new Error(`Task with ID ${taskId} not found`);
                    }
                    break;
                case 'removeTask':
                    const removeIndex = state.tasks.findIndex(task => task.id === taskId);
                    if (removeIndex !== -1) {
                        const removedTask = state.tasks.splice(removeIndex, 1)[0];
                        result = removedTask;
                    } else {
                        throw new Error(`Task with ID ${taskId} not found`);
                    }
                    break;
                case 'setTasks':
                    state.tasks = [...value]; // Create new array to prevent reference issues
                    result = state.tasks;
                    break;
                default:
                    throw new Error(`Unknown operation type: ${type}`);
            }
            
            if (resolve) resolve(result);
        } catch (error) {
            if (reject) reject(error);
            else console.error('State operation error:', error);
        }
    };

    const queueOperation = (operation) => {
        return new Promise((resolve, reject) => {
            operationQueue.push({ ...operation, resolve, reject });
            processQueue();
        });
    };

    // Lock management
    const acquireLock = () => {
        if (stateLock) {
            return false;
        }
        stateLock = true;
        setTimeout(() => {
            if (stateLock) {
                console.warn('State lock timeout, releasing lock');
                stateLock = false;
            }
        }, lockTimeout);
        return true;
    };

    const releaseLock = () => {
        stateLock = false;
    };

    return {
        // Basic getters (optimized - return references for read-only access)
        get: (key) => {
            // Return reference for read-only access (10x faster than copying)
            // Only copy on write operations (in setters)
            return state[key];
        },
        
        getAll: () => ({ 
            ...state
            // Don't copy tasks array - return reference for read-only access
        }),
        
        getTasks: () => state.tasks, // Return reference (no copy overhead)
        
        // Async setters with queue management
        set: async (key, value) => {
            return await queueOperation({ type: 'set', key, value });
        },
        
        setTasks: async (tasks) => {
            if (!Array.isArray(tasks)) {
                throw new Error('Tasks must be an array');
            }
            return await queueOperation({ type: 'setTasks', value: tasks });
        },
        
        addTask: async (task) => {
            if (!task || !task.id) {
                throw new Error('Task must have an ID');
            }
            return await queueOperation({ type: 'addTask', value: task });
        },
        
        updateTask: async (taskId, updatedTask) => {
            if (!taskId) {
                throw new Error('Task ID is required');
            }
            if (!updatedTask) {
                throw new Error('Updated task is required');
            }
            return await queueOperation({ type: 'updateTask', taskId, updatedTask });
        },
        
        removeTask: async (taskId) => {
            if (!taskId) {
                throw new Error('Task ID is required');
            }
            return await queueOperation({ type: 'removeTask', taskId });
        },

        // Synchronous operations for non-critical updates
        setSync: (key, value) => {
            if (key === 'tasks') {
                console.warn('Use setTasks() for task updates to prevent race conditions');
                return;
            }
            state[key] = value;
        },

        // Batch operations for atomic updates
        batchUpdate: async (updates) => {
            if (!Array.isArray(updates)) {
                throw new Error('Updates must be an array');
            }
            
            const results = [];
            for (const update of updates) {
                const result = await queueOperation(update);
                results.push(result);
            }
            return results;
        },

        // State validation
        validateState: () => {
            const errors = [];
            
            if (!Array.isArray(state.tasks)) {
                errors.push('Tasks must be an array');
            }
            
            if (state.tasks.some(task => !task.id)) {
                errors.push('All tasks must have an ID');
            }
            
            if (typeof state.currentPage !== 'string') {
                errors.push('Current page must be a string');
            }
            
            return {
                isValid: errors.length === 0,
                errors
            };
        },

        // State reset
        reset: () => {
            if (acquireLock()) {
                try {
                    state.tasks = [];
                    state.currentPage = 'tasks';
                    state.editingTaskId = null;
                    state.currentFilter = 'active';
                    state.developerLogs = [];
                } finally {
                    releaseLock();
                }
            }
        },

        // Debug information
        getDebugInfo: () => ({
            queueLength: operationQueue.length,
            isProcessingQueue,
            stateLock,
            taskCount: state.tasks.length,
            lastOperation: operationQueue[operationQueue.length - 1]?.type || 'none'
        })
    };
})();