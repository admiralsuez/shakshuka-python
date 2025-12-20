// Analytics dashboard updater - OPTIMIZED with consolidated endpoint
async function updateDashboardStats() {
    const tasks = (typeof AppState !== 'undefined' && typeof AppState.getTasks === 'function')
        ? (AppState.getTasks() || [])
        : ((AppState && AppState.get && AppState.get('tasks')) || []);

    const now = new Date();
    const todayStr = (() => {
        try {
            const yy = now.getFullYear();
            const mm = String(now.getMonth() + 1).padStart(2, '0');
            const dd = String(now.getDate()).padStart(2, '0');
            return `${yy}-${mm}-${dd}`;
        } catch (e) {
            return null;
        }
    })();

    const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    const completedToday = tasks.filter(t => {
        if (!t || !t.completed || !t.completed_at || !todayStr) return false;
        const s = String(t.completed_at);
        const d = s.includes('T') ? s.split('T')[0] : s;
        return d === todayStr;
    }).length;

    const overdue = tasks.filter(t => {
        if (!t || !t.due_date) return false;
        const d = new Date(t.due_date);
        return d < startOfToday && !(t.completed || t.struck_forever);
    }).length;

    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    // Local metrics
    setText('completed-today', completedToday);
    setText('expired-tasks', overdue);

    // Fetch all analytics from consolidated endpoint (single API call instead of multiple)
    try {
        if (typeof fetchWithFallback === 'function') {
            const summary = await fetchWithFallback('/api/analytics/summary', {
                fallbackValue: {
                    success: false,
                    tasks: { total: tasks.length, active: 0, expired: overdue, completed: 0 },
                    strikes: { today: 0, total: 0 },
                    streak: { current: 0, best: 0 },
                    completed_forever: 0,
                    settings_changes: 0,
                    tasks_added: tasks.length,
                    tasks_retried: 0
                },
                cacheTTL: 5000,
                showError: false
            });

            if (summary && summary.success) {
                // Update all dashboard stats from consolidated response
                setText('striked-today', summary.strikes.today);
                setText('streak-days', summary.streak.current);
                setText('tasks-added', summary.tasks_added);
                setText('completed-forever', summary.completed_forever);
                setText('settings-changes', summary.settings_changes);
                setText('tasks-retried', summary.tasks_retried);
                
                // Calculate productivity
                const productivity = summary.tasks.total > 0 
                    ? Math.round((summary.completed_forever / summary.tasks.total) * 100) 
                    : 0;
                setText('productivity-score', productivity + '%');
            }
        } else {
            // Fallback to old method if ErrorHandler not loaded yet
            const analyticsResp = await apiCall('/api/analytics');
            const a = await analyticsResp.json();
            if (a && a.success) {
                setText('striked-today', a.today_strikes || 0);
            }
            
            const completedForever = tasks.filter(t => (t.completed || t.struck_forever)).length;
            const total = tasks.length;
            const productivity = total > 0 ? Math.round((completedForever / total) * 100) : 0;
            
            setText('tasks-added', total);
            setText('completed-forever', completedForever);
            setText('productivity-score', productivity + '%');
            setText('streak-days', 0);
            setText('settings-changes', 0);
            setText('tasks-retried', 0);
        }
    } catch (e) {
        console.warn('Dashboard stats update failed, using fallback values:', e);
        // Use local fallback values
        const completedForever = tasks.filter(t => (t.completed || t.struck_forever)).length;
        const total = tasks.length;
        const productivity = total > 0 ? Math.round((completedForever / total) * 100) : 0;
        
        setText('striked-today', 0);
        setText('streak-days', 0);
        setText('tasks-added', total);
        setText('completed-forever', completedForever);
        setText('productivity-score', productivity + '%');
        setText('settings-changes', 0);
        setText('tasks-retried', 0);
    }
}

async function autoSave() {
    // Auto-save functionality - just trigger a save of current tasks
    if (AppState.get('isAuthenticated')) {
        try {
            const tasks = AppState.get('tasks') || [];
            // Don't send empty tasks array - only save if there are actual tasks
            if (tasks.length > 0) {
                // The backend auto-save worker handles saving tasks automatically
                // This frontend auto-save is mainly for UI state
                console.log('Auto-save: Tasks are being saved by backend worker');
            }
        } catch (error) {
            console.error('Auto-save failed:', error);
        }
    }
}

function calculateStreak() {
    const tasks = AppState.getTasks();
    const completedTasks = tasks.filter(task => task.completed && task.completed_at);
    
    if (completedTasks.length === 0) return 0;
    
    // Sort completed tasks by completion date (most recent first)
    completedTasks.sort((a, b) => new Date(b.completed_at) - new Date(a.completed_at));
    
    let streak = 0;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    // Check consecutive days starting from today
    for (let i = 0; i < completedTasks.length; i++) {
        const completedDate = new Date(completedTasks[i].completed_at);
        completedDate.setHours(0, 0, 0, 0);
        
        const expectedDate = new Date(today);
        expectedDate.setDate(today.getDate() - i);
        
        if (completedDate.getTime() === expectedDate.getTime()) {
            streak++;
        } else {
            break;
        }
    }
    
    return streak;
}

function calculateProductivityScore() {
    const tasks = AppState.getTasks();
    if (tasks.length === 0) return 0;
    
    const completedTasks = tasks.filter(task => task.completed).length;
    const totalTasks = tasks.length;
    
    return Math.round((completedTasks / totalTasks) * 100);
}
