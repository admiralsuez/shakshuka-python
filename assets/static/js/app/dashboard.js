// Analytics dashboard updater - OPTIMIZED with consolidated endpoint
let autoRefreshEnabled = false;
let heartbeatInterval = null;
let autoRefreshInterval = null;

function startHeartbeat() {
    // Heartbeat disabled - no longer tracking active users
    // if (heartbeatInterval) clearInterval(heartbeatInterval);
    // heartbeatInterval = setInterval(async () => {
    //     try {
    //         if (typeof fetch === 'function') {
    //             await fetch('/api/analytics/heartbeat', {
    //                 method: 'POST',
    //                 credentials: 'include',
    //                 headers: { 'Content-Type': 'application/json' },
    //                 body: JSON.stringify({})
    //             }).catch(() => {});
    //         }
    //     } catch (e) {
    //         // Silently ignore heartbeat failures
    //     }
    // }, 60000); // 1 minute
}

function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
    }
}

function startAutoRefresh() {
    // Refresh dashboard every 1 minute when enabled
    if (autoRefreshInterval) clearInterval(autoRefreshInterval);
    autoRefreshInterval = setInterval(() => {
        if (autoRefreshEnabled) {
            updateDashboardStats();
            // updateActiveUsersCount(); // Disabled - no longer tracking active users
        }
    }, 60000); // 1 minute
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

// DISABLED: Active users tracking endpoint
// async function updateActiveUsersCount() {
//     try {
//         let response = null;
//         if (typeof fetchWithFallback === 'function') {
//             response = await fetchWithFallback('/api/analytics/active-users', {
//                 fallbackValue: { active_users: 0 },
//                 cacheTTL: 0,
//                 showError: false
//             });
//         } else if (typeof apiCall === 'function') {
//             const resp = await apiCall('/api/analytics/active-users');
//             response = await resp.json().catch(() => ({ active_users: 0 }));
//         } else {
//             const resp = await fetch('/api/analytics/active-users', { credentials: 'include' });
//             response = await resp.json().catch(() => ({ active_users: 0 }));
//         }
//         
//         const el = document.getElementById('active-users-now');
//         if (el && response) {
//             el.textContent = response.active_users || 0;
//         }
//     } catch (e) {
//         // Silently ignore active users errors
//     }
// }
function updateActiveUsersCount() {
    // Disabled - no longer tracking active users
}

// DISABLED: Installed users tracking endpoint
// async function updateInstalledUsersCount() {
//     try {
//         let response = null;
//         if (typeof fetchWithFallback === 'function') {
//             response = await fetchWithFallback('/api/analytics/installed-users', {
//                 fallbackValue: { installed_users: 0 },
//                 cacheTTL: 300000, // Cache for 5 minutes (data doesn't change often)
//                 showError: false
//             });
//         } else if (typeof apiCall === 'function') {
//             const resp = await apiCall('/api/analytics/installed-users');
//             response = await resp.json().catch(() => ({ installed_users: 0 }));
//         } else {
//             const resp = await fetch('/api/analytics/installed-users', { credentials: 'include' });
//             response = await resp.json().catch(() => ({ installed_users: 0 }));
//         }
//         
//         const el = document.getElementById('installed-users-total');
//         if (el && response) {
//             el.textContent = response.installed_users || 0;
//         }
//     } catch (e) {
//         // Silently ignore installed users errors
//     }
// }
function updateInstalledUsersCount() {
    // Disabled - no longer tracking installed users
}

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

    const computeHoursWorked = () => {
        try {
            let minutes = 0;
            tasks.forEach((t) => {
                if (!t) return;
                const hasPlanned = t.planned_date || t.scheduled_date;
                if (!hasPlanned) return;
                const rawMinutes = t.scheduled_duration ?? t.estimated_duration ?? t.duration;
                const n = parseInt(rawMinutes || 0, 10);
                if (Number.isFinite(n) && n > 0) {
                    minutes += n;
                }
            });
            return minutes / 60;
        } catch (e) {
            return 0;
        }
    };

    const formatHours = (hours) => {
        if (!hours || !Number.isFinite(hours)) return '0';
        if (hours >= 100) return String(Math.round(hours));
        if (hours >= 10) return hours.toFixed(1);
        return hours.toFixed(1);
    };

    // Fetch all analytics from consolidated endpoint (single API call instead of multiple)
    try {
        // Try consolidated endpoint first (with or without ErrorHandler)
        let summary = null;
        
        if (typeof fetchWithFallback === 'function') {
            summary = await fetchWithFallback('/api/analytics/summary', {
                fallbackValue: null,
                cacheTTL: 5000,
                showError: false
            });
        } else if (typeof apiCall === 'function') {
            const response = await apiCall('/api/analytics/summary');
            summary = await response.json().catch(() => null);
        } else {
            const response = await fetch('/api/analytics/summary', { credentials: 'include' });
            summary = await response.json().catch(() => null);
        }

        if (summary && summary.success) {
            // Update all dashboard stats from consolidated response
            setText('striked-today', summary.strikes.today);
            setText('streak-days', (summary.completion_streak && typeof summary.completion_streak.current !== 'undefined')
                ? summary.completion_streak.current
                : (summary.streak ? summary.streak.current : 0));
            setText('strike-streak-days', (summary.strike_streak && typeof summary.strike_streak.current !== 'undefined')
                ? summary.strike_streak.current
                : 0);
            setText('tasks-added', summary.tasks_added);
            setText('completed-forever', summary.completed_forever);
            setText('settings-changes', summary.settings_changes);
            setText('tasks-retried', summary.tasks_retried);
            setText('tasks-deleted', summary.tasks_deleted || 0);
            setText('tasks-edited', summary.tasks_edited || 0);
            setText('tasks-with-dates', summary.tasks_with_dates || 0);
            const hoursWorked = computeHoursWorked();
            setText('tasks-with-time', formatHours(hoursWorked));
            setText('tasks-planned', summary.tasks_planned || 0);
            setText('daily-reset-count', summary.daily_reset_count || 0);
            
            // Calculate productivity
            const productivity = summary.tasks.total > 0 
                ? Math.round((summary.completed_forever / summary.tasks.total) * 100) 
                : 0;
            setText('productivity-score', productivity + '%');
        } else {
            // Fallback: calculate from local task data
            console.warn('Consolidated endpoint failed, using local calculations');
            const completedForever = tasks.filter(t => (t.completed || t.struck_forever)).length;
            const total = tasks.length;
            const productivity = total > 0 ? Math.round((completedForever / total) * 100) : 0;
            
            setText('striked-today', 0);
            setText('streak-days', 0);
            setText('strike-streak-days', 0);
            setText('tasks-added', total);
            setText('completed-forever', completedForever);
            setText('productivity-score', productivity + '%');
            setText('settings-changes', 0);
            setText('tasks-retried', 0);
            setText('tasks-deleted', 0);
            setText('tasks-edited', 0);
            setText('tasks-with-dates', tasks.filter(t => t && t.due_date).length);
            const hoursWorked = computeHoursWorked();
            setText('tasks-with-time', formatHours(hoursWorked));
            setText('tasks-planned', tasks.filter(t => t && t.planned_date).length);
        }
    } catch (e) {
        console.error('Dashboard stats update failed:', e);
        // Use local fallback values
        const completedForever = tasks.filter(t => (t.completed || t.struck_forever)).length;
        const total = tasks.length;
        const productivity = total > 0 ? Math.round((completedForever / total) * 100) : 0;
        
        setText('striked-today', 0);
        setText('streak-days', 0);
        setText('strike-streak-days', 0);
        setText('tasks-added', total);
        setText('completed-forever', completedForever);
        setText('productivity-score', productivity + '%');
        setText('settings-changes', 0);
        setText('tasks-retried', 0);
        setText('tasks-deleted', 0);
        setText('tasks-edited', 0);
        setText('tasks-with-dates', tasks.filter(t => t && t.due_date).length);
        const hoursWorked = computeHoursWorked();
        setText('tasks-with-time', formatHours(hoursWorked));
        setText('tasks-planned', tasks.filter(t => t && t.planned_date).length);
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

// Initialize analytics page with auto-refresh
function initializeAnalyticsPage() {
    // Heartbeat disabled - no longer tracking active users
    // startHeartbeat();
    
    // Set up auto-refresh toggle
    const toggleEl = document.getElementById('analytics-auto-refresh');
    if (toggleEl) {
        // Load saved preference from localStorage
        const savedPref = localStorage.getItem('analytics-auto-refresh') === 'true';
        toggleEl.checked = savedPref;
        autoRefreshEnabled = savedPref;
        
        toggleEl.addEventListener('change', (e) => {
            autoRefreshEnabled = e.target.checked;
            localStorage.setItem('analytics-auto-refresh', autoRefreshEnabled);
            
            if (autoRefreshEnabled) {
                // When enabling, do an immediate refresh then start interval
                updateDashboardStats();
                // updateActiveUsersCount(); // Disabled - no longer tracking active users
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
        
        // Start auto-refresh if it was enabled previously
        if (autoRefreshEnabled) {
            startAutoRefresh();
        }
    }
    
    // Active users tracking disabled
    // updateActiveUsersCount();
    
    // Installed users tracking disabled
    // updateInstalledUsersCount();
}

// Hook into page visibility to stop auto-refresh when tab is hidden
if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            // stopHeartbeat(); // Disabled - no longer tracking active users
            stopAutoRefresh();
        } else {
            // startHeartbeat(); // Disabled - no longer tracking active users
            if (autoRefreshEnabled) {
                startAutoRefresh();
            }
        }
    });
}

// Initialize when analytics page is shown
if (typeof window !== 'undefined') {
    // Patch page switcher to init analytics when page loads
    const origShowPage = window.showPage;
    if (typeof origShowPage === 'function') {
        window.showPage = function(pageName) {
            const result = origShowPage.call(this, pageName);
            if (pageName === 'analytics') {
                setTimeout(initializeAnalyticsPage, 100);
            }
            return result;
        };
    }
}
