let currentStrikeTaskId = null;
let currentStrikeReportHistoryTaskId = null;

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function displayLogs() {
    const logsContent = document.getElementById('logs-content');
    if (!logsContent) return;

    const logs = AppState.get('developerLogs');
    if (logs.length === 0) {
        logsContent.textContent = 'No logs available';
        return;
    }

    const logsHtml = logs.map(log => {
        return `<div class="log-entry ${log.level}">
            <div class="log-timestamp">[${log.timestamp}]</div>
            <div class="log-message">${log.message}</div>
        </div>`;
    }).join('');

    logsContent.innerHTML = logsHtml;
}

function closeStrikeReportHistoryModal() {
    const modal = document.getElementById('strike-report-history-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    const content = document.getElementById('strike-report-history-content');
    if (content) {
        content.innerHTML = '';
    }
    currentStrikeReportHistoryTaskId = null;
}

function toggleStrikeReportHistoryItem(btn) {
    const wrapper = btn ? btn.closest('.strike-report-history-item') : null;
    if (!wrapper) return;
    const body = wrapper.querySelector('.strike-report-history-body');
    if (!body) return;
    const expanded = wrapper.classList.toggle('expanded');
    btn.textContent = expanded ? 'Show less' : 'Read more';
}

async function openStrikeReportHistoryModal(taskId) {
    currentStrikeReportHistoryTaskId = taskId;
    const modal = document.getElementById('strike-report-history-modal');
    const content = document.getElementById('strike-report-history-content');
    if (!modal || !content) return;

    modal.classList.add('active');
    modal.style.display = 'flex';

    content.innerHTML = `
        <div class="loading-changelog">
            <div class="loading-spinner"></div>
            <p>Loading reports...</p>
        </div>
    `;

    try {
        const url = `/api/tasks/${encodeURIComponent(taskId)}/strike-reports?limit=200`;
        const response = (typeof window.apiCall === 'function')
            ? await window.apiCall(url)
            : await fetch(url, { credentials: 'include' });

        const data = await response.json().catch(() => null);
        if (!response.ok) {
            const msg = (data && data.error) ? data.error : `Request failed (${response.status})`;
            throw new Error(msg);
        }
        if (!data || data.success !== true) {
            throw new Error((data && data.error) || 'Failed to load reports');
        }

        const items = Array.isArray(data.items) ? data.items : [];
        if (!items.length) {
            content.innerHTML = '<p style="color: var(--text-secondary);">No strike reports logged yet for this task.</p>';
            return;
        }

        const html = items.map(item => {
            const createdAt = escapeHtml(item.created_at || '');
            const day = escapeHtml(item.day || '');
            const strikeNumber = escapeHtml(item.strike_number || '');
            const report = (item.report || '').trim();
            const safeReport = escapeHtml(report);
            const needsMore = report.split(/\r?\n/).length > 2 || report.length > 180;

            return `
                <div class="strike-report-history-item" data-id="${escapeHtml(item.id)}">
                    <div class="strike-report-history-meta">
                        <div class="strike-report-history-date">${day}</div>
                        <div class="strike-report-history-strike">Strike ${strikeNumber}</div>
                        <div class="strike-report-history-time">${createdAt}</div>
                    </div>
                    <div class="strike-report-history-body">${safeReport || '<em>No report</em>'}</div>
                    ${needsMore ? '<button type="button" class="strike-report-history-more" onclick="toggleStrikeReportHistoryItem(this)">Read more</button>' : ''}
                </div>
            `;
        }).join('');

        content.innerHTML = `<div class="strike-report-history-list">${html}</div>`;
    } catch (e) {
        console.error('Failed to load strike report history', e);
        const msg = e && e.message ? escapeHtml(e.message) : 'Unable to load strike report history.';
        content.innerHTML = `<p style="color: var(--text-secondary);">${msg}</p>`;
    }
}

function openLogsModal() {
    document.getElementById('logs-modal').classList.add('active');
    displayLogs();
    addLog('info', 'Developer logs modal opened');
}

function closeLogsModal() {
    document.getElementById('logs-modal').classList.remove('active');
}

function canStrikeTask(task) {
    const today = new Date().toDateString();
    const taskStrikesToday = task.daily_strikes || {};

    // Check if task has been struck twice today
    return (taskStrikesToday[today] || 0) < 2;
}

function getTaskStrikesToday(task) {
    const today = new Date().toDateString();
    return (task.daily_strikes || {})[today] || 0;
}

function openStrikeModal(taskId) {
    console.log('Opening strike modal for task:', taskId);
    currentStrikeTaskId = taskId;
    // Clear the report field
    const modal = document.getElementById('strike-modal');
    const reportEl = document.getElementById('strike-report');
    if (reportEl) reportEl.value = '';
    if (modal) {
        modal.classList.add('active');
        modal.style.display = 'flex'; // ensure visible even if CSS expects inline style
    }
    if (reportEl) reportEl.focus();
    addLog('info', `Opening strike modal for task ${taskId}`);
}

function closeStrikeModal() {
    const modal = document.getElementById('strike-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
    const reportEl = document.getElementById('strike-report');
    if (reportEl) reportEl.value = '';
    currentStrikeTaskId = null;
}

async function strikeTaskToday() {
    const report = document.getElementById('strike-report').value.trim();

    if (!currentStrikeTaskId) {
        showNotification('No task selected', 'error');
        return;
    }

    // Check if task can still be struck today (guard against missing task state)
    const tasks = AppState.get('tasks') || [];
    const task = tasks.find(t => t.id === currentStrikeTaskId);
    if (task && !canStrikeTask(task)) {
        showNotification('Maximum strikes reached for today', 'error');
        return;
    }

    try {
        console.log('Attempting to strike task:', currentStrikeTaskId, 'with report:', report);

        const response = await fetch(`/api/tasks/${currentStrikeTaskId}/strike`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: 'today',
                report: report
            })
        });

        console.log('Strike response status:', response.status);

        if (response.ok) {
            const updatedTask = await response.json().catch(() => null);
            closeStrikeModal();
            // Optimistically update AppState immediately
            try {
                if (updatedTask && window.AppState && AppState.updateTask) {
                    await AppState.updateTask(currentStrikeTaskId, updatedTask).catch(async () => {
                        if (AppState.addTask) {
                            await AppState.addTask(updatedTask);
                        }
                    });
                }
            } catch (e) { /* noop */ }
            // Full reload as safety
            await loadTasks();
            updateDashboardStats();
            try {
                if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.refresh === 'function') {
                    window.DailyPlannerV2.refresh();
                }
            } catch (e) { /* noop */ }
            // If currently on tasks page, re-render immediately
            try {
                if (AppState.get && AppState.get('currentPage') === 'tasks') {
                    renderTasks();
                }
            } catch (e) { /* noop */ }
            showNotification('Task struck for today! 📝', 'success');
            addLog('success', `Task ${currentStrikeTaskId} struck for today: ${report}`);
        } else {
            const errorData = await response.json();
            console.error('Strike error response:', errorData);

            // Handle specific error for maximum strikes reached
            if (errorData.error && errorData.error.includes('Maximum strikes reached')) {
                showNotification('Maximum strikes reached for today', 'error');
                closeStrikeModal();
                // Refresh tasks to update UI
                await loadTasks();
            } else {
                throw new Error(errorData.error || 'Failed to strike task');
            }
        }
    } catch (error) {
        console.error('Error striking task:', error);
        addLog('error', `Failed to strike task ${currentStrikeTaskId}: ${error.message}`);
        showNotification(`Error striking task: ${error.message}`, 'error');
    }
}

async function strikeTaskForever() {
    const report = document.getElementById('strike-report').value.trim();

    if (!currentStrikeTaskId) {
        showNotification('No task selected', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/tasks/${currentStrikeTaskId}/strike`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: 'forever',
                report: report
            })
        });

        if (response.ok) {
            const updatedTask = await response.json().catch(() => null);
            closeStrikeModal();
            try {
                if (updatedTask && window.AppState && AppState.updateTask) {
                    await AppState.updateTask(currentStrikeTaskId, updatedTask).catch(async () => {
                        if (AppState.addTask) {
                            await AppState.addTask(updatedTask);
                        }
                    });
                }
            } catch (e) { /* noop */ }
            await loadTasks();
            updateDashboardStats();
            try {
                if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.refresh === 'function') {
                    window.DailyPlannerV2.refresh();
                }
            } catch (e) { /* noop */ }
            try {
                if (AppState.get && AppState.get('currentPage') === 'tasks') {
                    renderTasks();
                }
            } catch (e) { /* noop */ }
            showNotification('Task completed forever! 🎉', 'success');
            addLog('success', `Task ${currentStrikeTaskId} struck forever: ${report}`);
        } else {
            throw new Error('Failed to strike task');
        }
    } catch (error) {
        console.error('Error striking task:', error);
        addLog('error', `Failed to strike task ${currentStrikeTaskId}: ${error.message}`);
        showNotification('Error striking task', 'error');
    }
}

async function undoStrike(taskId) {
    if (!confirm('Are you sure you want to undo this strike?')) {
        return;
    }

    try {
        const response = await fetch(`/api/tasks/${taskId}/undo-strike`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });

        if (response.ok) {
            await loadTasks();
            updateDashboardStats();
            // After undoing a strike, a task may move from expired/completed
            // back to active; refresh project filter options.
            try {
                if (window.Tasks && typeof Tasks.updateProjectFilterOptions === 'function') {
                    Tasks.updateProjectFilterOptions();
                }
            } catch (e) { /* no-op */ }
            showNotification('Strike undone successfully! ↩️', 'success');
            addLog('success', `Task ${taskId} strike undone`);
        } else {
            throw new Error('Failed to undo strike');
        }
    } catch (error) {
        console.error('Error undoing strike:', error);
        addLog('error', `Failed to undo strike for task ${taskId}: ${error.message}`);
        showNotification('Error undoing strike', 'error');
    }
}
