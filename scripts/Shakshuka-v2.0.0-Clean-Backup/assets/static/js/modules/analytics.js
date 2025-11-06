/**
 * Analytics Module - Handles statistics, charts, and productivity metrics
 */

const Analytics = (function() {
    'use strict';
    
    let chartInstances = {};
    
    // ==================== Initialization ====================
    
    function initialize() {
        loadAnalytics();
    }
    
    // ==================== Data Loading ====================
    
    async function loadAnalytics() {
        try {
            const response = await fetch('/api/analytics');
            if (response.ok) {
                const data = await response.json();
                renderAnalytics(data);
            }
        } catch (error) {
            console.error('Error loading analytics:', error);
            UI.showError('Failed to load analytics');
        }
    }
    
    async function getTaskStats() {
        try {
            const response = await fetch('/api/tasks/stats');
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Error loading task stats:', error);
        }
        return null;
    }
    
    // ==================== Rendering ====================
    
    function renderAnalytics(data) {
        renderOverviewStats(data.overview);
        renderCompletionChart(data.completion);
        renderPriorityChart(data.priority);
        renderProductivityTrend(data.trend);
    }
    
    function renderOverviewStats(stats) {
        if (!stats) return;
        
        updateStatCard('total-tasks', stats.total);
        updateStatCard('completed-tasks', stats.completed);
        updateStatCard('in-progress-tasks', stats.inProgress);
        updateStatCard('completion-rate', `${stats.completionRate}%`);
    }
    
    function updateStatCard(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }
    
    // ==================== Chart Rendering ====================
    
    function renderCompletionChart(data) {
        const canvas = document.getElementById('completion-chart');
        if (!canvas) return;
        
        // Destroy existing chart
        if (chartInstances.completion) {
            chartInstances.completion.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        chartInstances.completion = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Completed', 'In Progress', 'Pending'],
                datasets: [{
                    data: [data.completed, data.inProgress, data.pending],
                    backgroundColor: [
                        '#4CAF50',
                        '#FF9800',
                        '#9E9E9E'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom'
                    }
                }
            }
        });
    }
    
    function renderPriorityChart(data) {
        const canvas = document.getElementById('priority-chart');
        if (!canvas) return;
        
        if (chartInstances.priority) {
            chartInstances.priority.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        chartInstances.priority = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Low', 'Medium', 'High', 'Urgent'],
                datasets: [{
                    label: 'Tasks by Priority',
                    data: [data.low, data.medium, data.high, data.urgent],
                    backgroundColor: [
                        '#4CAF50',
                        '#FFC107',
                        '#FF9800',
                        '#F44336'
                    ]
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    function renderProductivityTrend(data) {
        const canvas = document.getElementById('productivity-chart');
        if (!canvas) return;
        
        if (chartInstances.productivity) {
            chartInstances.productivity.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        chartInstances.productivity = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.dates,
                datasets: [{
                    label: 'Tasks Completed',
                    data: data.completed,
                    borderColor: '#4CAF50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    tension: 0.4,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            stepSize: 1
                        }
                    }
                },
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    // ==================== Export Functions ====================
    
    async function exportAnalytics(format = 'json') {
        try {
            const response = await fetch(`/api/analytics/export?format=${format}`);
            if (response.ok) {
                const blob = await response.blob();
                downloadBlob(blob, `analytics-${Date.now()}.${format}`);
                UI.showSuccess('Analytics exported successfully');
            } else {
                UI.showError('Failed to export analytics');
            }
        } catch (error) {
            console.error('Error exporting analytics:', error);
            UI.showError('Error exporting analytics');
        }
    }
    
    function downloadBlob(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
    }
    
    // ==================== Cleanup ====================
    
    function cleanup() {
        // Destroy all chart instances
        for (const key in chartInstances) {
            if (chartInstances[key]) {
                chartInstances[key].destroy();
            }
        }
        chartInstances = {};
    }
    
    // ==================== Public API ====================
    
    return {
        initialize,
        loadAnalytics,
        getTaskStats,
        exportAnalytics,
        cleanup
    };
})();

// Expose to global scope
window.Analytics = Analytics;

