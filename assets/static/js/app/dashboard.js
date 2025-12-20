// Analytics dashboard updater
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

    const struckTodayFromState = tasks.filter(t => Boolean(t && t.struck_today)).length;

    const completedForever = tasks.filter(t => (t.completed || t.struck_forever)).length;
    const total = tasks.length;
    const overdue = tasks.filter(t => {
        if (!t || !t.due_date) return false;
        const d = new Date(t.due_date);
        return d < startOfToday && !(t.completed || t.struck_forever);
    }).length;

    // productivity = completed forever / total
    const productivity = total > 0 ? Math.round((completedForever / total) * 100) : 0;

    // tasks added = total
    const settingsChanges = parseInt(localStorage.getItem('settings_changes_count') || '0', 10);

    const setText = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    // Local/task-derived metrics
    setText('completed-today', completedToday);
    setText('expired-tasks', overdue);
    setText('productivity-score', productivity + '%');

    // Fetch streak and strikes from backend API for consistency with recap modal
    let strikesToday = struckTodayFromState;
    let streakDays = 0;
    try {
        if (typeof apiCall === 'function') {
            // Get today's strikes
            const analyticsResp = await apiCall('/api/analytics');
            const a = await analyticsResp.json();
            if (a && a.success) {
                strikesToday = (a.today_strikes ?? strikesToday);
            }

            // Get streak from daily-recap endpoint (uses same calculation as recap modal)
            const yesterday = new Date();
            yesterday.setDate(yesterday.getDate() - 1);
            const yy = yesterday.getFullYear();
            const mm = String(yesterday.getMonth() + 1).padStart(2, '0');
            const dd = String(yesterday.getDate()).padStart(2, '0');
            const yesterdayStr = `${yy}-${mm}-${dd}`;
            
            const recapResp = await apiCall(`/api/analytics/daily-recap?day=${encodeURIComponent(yesterdayStr)}`);
            const recap = await recapResp.json();
            if (recap && recap.success) {
                streakDays = recap.streak_days ?? 0;
            }
        }
    } catch (e) {
        // ignore; fallback already set
    }
    setText('striked-today', strikesToday);
    setText('streak-days', streakDays);

    // New widgets
    setText('tasks-added', total);
    setText('completed-forever', completedForever);
    setText('settings-changes', settingsChanges);
    
    // Tasks retried (will be fetched from backend when retry tracking is implemented)
    setText('tasks-retried', 0);
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
