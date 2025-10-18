// State Management Module
const AppState = (() => {
    const state = {
        currentPage: 'tasks',
        tasks: [],
        currentDate: new Date(),
        editingTaskId: null,
        currentSettings: {},
        currentLayout: 'list',
        dailyResetTimer: null,
        developerLogs: [],
        currentFilter: 'active',
        isAuthenticated: false,
        user: null,
        sessionId: null
    };

    return {
        get: (key) => state[key],
        set: (key, value) => { state[key] = value; },
        getAll: () => ({ ...state }),
        getTasks: () => [...state.tasks],
        setTasks: (tasks) => { state.tasks = tasks; },
        addTask: (task) => { state.tasks.unshift(task); },
        updateTask: (taskId, updatedTask) => {
            const index = state.tasks.findIndex(task => task.id === taskId);
            if (index !== -1) {
                state.tasks[index] = updatedTask;
            }
        },
        removeTask: (taskId) => {
            state.tasks = state.tasks.filter(task => task.id !== taskId);
        }
    };
})();
