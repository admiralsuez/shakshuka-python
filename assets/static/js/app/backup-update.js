// Update and Backup Management Functions
let currentUpdateInfo = null;
let updatePollInterval = null;
let isUpdateDownloading = false;
let lastUpdateStatus = null;

// UpdateProgressPoller class for exponential backoff polling
class UpdateProgressPoller {
    constructor() {
        this.pollingTimer = null;
        this.isPolling = false;
        this.pollInterval = 800;  // Start at 800ms
        this.nextCheckTime = Date.now();
        this.maxInterval = 4000;  // Max 4 seconds
        this.maxWaitTime = 600000;  // 10 minutes
        this.startTime = Date.now();
    }
    
    start() {
        if (this.pollingTimer) return;
        
        this.pollingTimer = setInterval(() => {
            this.checkProgress();
        }, 100);  // Check every 100ms if it's time
    }
    
    async checkProgress() {
        const now = Date.now();
        
        // Skip if not time yet
        if (now < this.nextCheckTime) return;
        
        // Skip if already polling
        if (this.isPolling) return;
        
        // Give up if exceeded max wait time
        if (now - this.startTime > this.maxWaitTime) {
            this.stop();
            return;
        }
        
        this.isPolling = true;
        
        try {
            const res = await fetch('/api/updates/progress');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            
            const status = await res.json();
            const st = (status.status || '').toLowerCase();
            
            if (st === 'downloading') {
                const pct = Math.max(0, Math.min(100, status.progress || 0));
                const progressFill = document.getElementById('github-progress-fill');
                const progressText = document.getElementById('github-progress-text');
                
                if (progressFill) progressFill.style.width = pct + '%';
                if (progressText) {
                    const downloadedMB = ((status.downloaded || 0) / (1024 * 1024)).toFixed(1);
                    const totalMB = status.total ? ((status.total) / (1024 * 1024)).toFixed(1) : '...';
                    progressText.textContent = `Downloading update... ${pct}% (${downloadedMB} / ${totalMB} MB)`;
                }
                
                // Reset interval on progress
                this.pollInterval = 800;
                this.nextCheckTime = now + this.pollInterval;
            } else if (st === 'ready') {
                // Download complete
                this.stop();
                const progressFill = document.getElementById('github-progress-fill');
                const progressText = document.getElementById('github-progress-text');
                if (progressFill) progressFill.style.width = '100%';
                if (progressText) progressText.textContent = 'Download complete.';
            } else if (st === 'failed' || st === 'canceled') {
                this.stop();
                const progressText = document.getElementById('github-progress-text');
                if (progressText) progressText.textContent = st === 'failed' ? 'Download failed.' : 'Download canceled.';
            } else {
                // Exponential backoff: 800ms → 1.2s → 1.8s → 2.7s → 4s
                this.pollInterval = Math.min(
                    this.pollInterval * 1.5,
                    this.maxInterval
                );
                this.nextCheckTime = now + this.pollInterval;
            }
        } catch (e) {
            console.error('Progress poll error:', e);
            // Exponential backoff on error
            this.pollInterval = Math.min(
                this.pollInterval * 1.5,
                this.maxInterval
            );
            this.nextCheckTime = now + this.pollInterval;
        } finally {
            this.isPolling = false;
        }
    }
    
    stop() {
        if (this.pollingTimer) {
            clearInterval(this.pollingTimer);
            this.pollingTimer = null;
        }
    }
}

// Unified update check handler for the Settings "Check for Updates" button.
// This now delegates to the GitHub-based check so that any newer version
// published on GitHub will surface via the GitHub update modal.
async function checkForUpdates() {
    return checkGitHubUpdate();
}

// ── Excel Export ──
function openExportExcelModal() {
    const modal = document.getElementById('export-excel-modal');
    if (!modal) return;
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);
    const startEl = document.getElementById('export-start-date');
    const endEl = document.getElementById('export-end-date');
    if (startEl) startEl.value = thirtyDaysAgo.toISOString().split('T')[0];
    if (endEl) endEl.value = today.toISOString().split('T')[0];
    modal.style.display = 'flex';
    modal.classList.add('active');
    
    // Load projects
    loadProjectsForFilter();
    
    // Setup quick date preset buttons
    setupDatePresets();
}

function closeExportExcelModal() {
    const modal = document.getElementById('export-excel-modal');
    if (modal) {
        modal.classList.remove('active');
        modal.style.display = 'none';
    }
}

function loadProjectsForFilter() {
    const projectList = document.getElementById('project-filter-list');
    if (!projectList) return;
    
    // Get unique projects from current tasks
    const tasks = window.AppState ? window.AppState.getTasks() : [];
    const projects = new Set();
    
    tasks.forEach(task => {
        if (task.project && task.project.trim()) {
            projects.add(task.project.trim());
        }
    });
    
    // Sort projects alphabetically
    const sortedProjects = Array.from(projects).sort();
    
    if (sortedProjects.length === 0) {
        projectList.innerHTML = '<p style="color: var(--text-secondary); font-size: 0.85rem;">No projects found.</p>';
        return;
    }
    
    // Create checkboxes for each project
    projectList.innerHTML = sortedProjects.map(project => `
        <label style="display: flex; align-items: center; gap: 0.5rem; cursor: pointer; padding: 0.3rem 0;">
            <input type="checkbox" class="project-filter-checkbox" value="${project}" checked>
            <span>${project}</span>
        </label>
    `).join('');
}

function setupDatePresets() {
    const today = new Date();
    const startEl = document.getElementById('export-start-date');
    const endEl = document.getElementById('export-end-date');
    
    const setDateRange = (startDate, endDate) => {
        if (startEl) startEl.value = startDate.toISOString().split('T')[0];
        if (endEl) endEl.value = endDate.toISOString().split('T')[0];
    };
    
    // Today
    const presetToday = document.getElementById('preset-today');
    if (presetToday) {
        presetToday.addEventListener('click', (e) => {
            e.preventDefault();
            setDateRange(today, today);
        });
    }
    
    // Last 7 Days
    const presetWeek = document.getElementById('preset-week');
    if (presetWeek) {
        presetWeek.addEventListener('click', (e) => {
            e.preventDefault();
            const sevenDaysAgo = new Date();
            sevenDaysAgo.setDate(today.getDate() - 7);
            setDateRange(sevenDaysAgo, today);
        });
    }
    
    // This Month
    const presetThisMonth = document.getElementById('preset-this-month');
    if (presetThisMonth) {
        presetThisMonth.addEventListener('click', (e) => {
            e.preventDefault();
            const firstDayOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
            setDateRange(firstDayOfMonth, today);
        });
    }
    
    // Last 30 Days
    const presetMonth = document.getElementById('preset-month');
    if (presetMonth) {
        presetMonth.addEventListener('click', (e) => {
            e.preventDefault();
            const thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(today.getDate() - 30);
            setDateRange(thirtyDaysAgo, today);
        });
    }
    
    // Last 90 Days
    const presetQuarter = document.getElementById('preset-quarter');
    if (presetQuarter) {
        presetQuarter.addEventListener('click', (e) => {
            e.preventDefault();
            const ninetyDaysAgo = new Date();
            ninetyDaysAgo.setDate(today.getDate() - 90);
            setDateRange(ninetyDaysAgo, today);
        });
    }
    
    // Last Year
    const presetYear = document.getElementById('preset-year');
    if (presetYear) {
        presetYear.addEventListener('click', (e) => {
            e.preventDefault();
            const oneYearAgo = new Date();
            oneYearAgo.setFullYear(today.getFullYear() - 1);
            setDateRange(oneYearAgo, today);
        });
    }
    
    // All Time
    const presetAll = document.getElementById('preset-all');
    if (presetAll) {
        presetAll.addEventListener('click', (e) => {
            e.preventDefault();
            if (startEl) startEl.value = '';
            if (endEl) endEl.value = '';
        });
    }
    
    // Select All Projects
    const selectAllBtn = document.getElementById('select-all-projects');
    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.project-filter-checkbox').forEach(cb => {
                cb.checked = true;
            });
        });
    }
    
    // Clear All Projects
    const clearAllBtn = document.getElementById('clear-all-projects');
    if (clearAllBtn) {
        clearAllBtn.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.project-filter-checkbox').forEach(cb => {
                cb.checked = false;
            });
        });
    }
}

function exportExcelReport() {
    const startDate = (document.getElementById('export-start-date') || {}).value || '';
    const endDate = (document.getElementById('export-end-date') || {}).value || '';
    
    // Get selected projects
    const selectedProjects = Array.from(document.querySelectorAll('.project-filter-checkbox:checked'))
        .map(cb => cb.value);
    
    let url = '/api/tasks/export-excel?';
    if (startDate) url += 'start_date=' + encodeURIComponent(startDate) + '&';
    if (endDate) url += 'end_date=' + encodeURIComponent(endDate) + '&';
    if (selectedProjects.length > 0) {
        url += 'projects=' + encodeURIComponent(selectedProjects.join(',')) + '&';
    }
    
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    closeExportExcelModal();
    if (typeof showNotification === 'function') showNotification('Excel report exported! 📊', 'success');
}

(function initExportExcelHandlers() {
    function setup() {
        var btn = document.getElementById('export-excel-btn');
        if (btn) btn.addEventListener('click', openExportExcelModal);
        var closeBtn = document.getElementById('close-export-excel-modal');
        if (closeBtn) closeBtn.addEventListener('click', closeExportExcelModal);
        var cancelBtn = document.getElementById('cancel-export-excel');
        if (cancelBtn) cancelBtn.addEventListener('click', closeExportExcelModal);
        var confirmBtn = document.getElementById('confirm-export-excel');
        if (confirmBtn) confirmBtn.addEventListener('click', exportExcelReport);
        var modal = document.getElementById('export-excel-modal');
        if (modal) modal.addEventListener('click', function(e) { if (e.target === modal) closeExportExcelModal(); });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setup);
    } else {
        setup();
    }
})();

async function checkGitHubUpdate() {
    try {
        const branchElement = document.getElementById('github-branch');
        const branch = branchElement ? branchElement.value : 'main';
        showNotification('Checking GitHub for updates...', 'info');

        let result = null;
        if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
            result = await window.Utils.apiRequestJson(
                '/api/github/check-update',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch: branch })
                },
                { expectObject: true, retries: 1, retryDelayMs: 750 }
            );
        } else {
            const response = await fetch('/api/github/check-update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ branch: branch })
            });
            if (!response.ok) {
                throw new Error(`Update check failed (${response.status})`);
            }
            result = await response.json();
        }

        const updateAvailable = !!(result && result.update_available);
        const currentVersion = (result && typeof result.current_version === 'string') ? result.current_version : '';

        if (updateAvailable) {
            showGitHubUpdateModal(result);
            showNotification('GitHub update available!', 'success');
        } else {
            showNotification(`You are up to date!${currentVersion ? ` (${currentVersion})` : ''}`, 'success');
        }
    } catch (error) {
        console.error('Error checking GitHub update:', error);
        const msg = (error && error.message) ? error.message : 'Error checking GitHub for updates';
        showNotification(msg, 'error');
    }
}

async function maybeAutoCheckForUpdatesWeekly() {
    try {
        const now = Date.now();
        const storageKey = 'shakshuka_last_update_check';
        const lastRaw = localStorage.getItem(storageKey);
        const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

        if (lastRaw) {
            const last = parseInt(lastRaw, 10);
            if (!isNaN(last) && (now - last) < SEVEN_DAYS_MS) {
                return; // already checked within the last week
            }
        }

        // Mark attempt time up-front so repeated failures don't spam
        localStorage.setItem(storageKey, String(now));

        const branchElement = document.getElementById('github-branch');
        const branch = branchElement ? branchElement.value : 'main';

        let result = null;
        if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
            result = await window.Utils.apiRequestJson(
                '/api/github/check-update',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch })
                },
                { expectObject: true, retries: 0 }
            );
        } else {
            const response = await fetch('/api/github/check-update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ branch })
            });

            if (!response.ok) {
                return;
            }

            result = await response.json();
        }
        if (!result.update_available) {
            return;
        }

        // Persistent, clickable toast for weekly auto-check
        showNotification('new update, click me', 'info', {
            persistent: true,
            onClick: () => {
                try {
                    // Reuse the already-fetched release info for the modal
                    showGitHubUpdateModal(result);
                } catch (e) {
                    // Fallback to a regular explicit check if something goes wrong
                    try { checkGitHubUpdate(); } catch (_) {}
                }
            }
        });
    } catch (e) {
        console.error('Weekly auto-update check failed:', e);
    }
}

let updateProgressPoller = null;

async function downloadGitHubUpdate() {
    try {
        const branchElement = document.getElementById('github-branch');
        const branch = branchElement ? branchElement.value : 'main';
        showNotification('Downloading update from GitHub...', 'info');

        // Show progress UI in the GitHub update modal
        const progressDiv = document.getElementById('github-update-progress');
        const progressFill = document.getElementById('github-progress-fill');
        const progressText = document.getElementById('github-progress-text');
        if (progressDiv && progressFill && progressText) {
            progressDiv.style.display = 'block';
            progressFill.style.width = '0%';
            progressText.textContent = 'Starting download...';
        }

        // Start polling with exponential backoff
        updateProgressPoller = new UpdateProgressPoller();
        updateProgressPoller.start();

        let result = null;
        if (window.Utils && typeof window.Utils.apiRequestJson === 'function') {
            result = await window.Utils.apiRequestJson(
                '/api/github/download-update',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ branch: branch })
                },
                { expectObject: true, retries: 0, timeoutMs: 60000 }
            );
        } else {
            const response = await fetch('/api/github/download-update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ branch: branch })
            });
            if (!response.ok) {
                throw new Error(`Update download failed (${response.status})`);
            }
            result = await response.json();
        }

        if (result.success) {
            const path = result.installer_path || 'the downloaded installer file';
            // Short success snack about the update itself
            showNotification('Update installer downloaded. Please close Shakshuka and run the installer to finish updating.', 'success');

            // Persistent, clickable toast that shows where the file went and
            // lets the user open the folder directly.
            const friendlyPath = path;
            const safeMessage = `Download finished to \"${friendlyPath}\" (click to open folder)`;
            showNotification(safeMessage, 'info', {
                persistent: true,
                onClick: () => {
                    try {
                        // Ask the backend to open the downloads folder using the
                        // same logic it used when saving the installer.
                        fetch('/api/github/open-downloads-folder', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({})
                        }).catch((e) => {
                            console.error('Failed to request opening downloads folder', e);
                        });
                    } catch (e) {
                        console.error('Failed to trigger folder open for installer path', e);
                    }
                }
            });

            // Close any open modals
            try { closeUpdateModal(); } catch (_) {}
            try { closeGitHubUpdateModal(); } catch (_) {}
        } else {
            if (updateProgressPoller) {
                updateProgressPoller.stop();
            }
            if (progressDiv && progressText) {
                progressText.textContent = 'Download failed.';
            }
            showNotification(`Update failed: ${(result && result.error) ? result.error : 'Unknown error'}`, 'error');
        }
    } catch (error) {
        console.error('Error downloading GitHub update:', error);
        if (updateProgressPoller) {
            updateProgressPoller.stop();
        }
        const progressText = document.getElementById('github-progress-text');
        if (progressText) {
            progressText.textContent = 'Download failed.';
        }
        showNotification(error && error.message ? error.message : 'Error downloading update from GitHub', 'error');
    }
}

function showGitHubUpdateModal(updateInfo) {
    const modal = document.getElementById('github-update-modal');
    if (!modal) {
        // Create modal if it doesn't exist
        createGitHubUpdateModal();
    }

    const modalElement = document.getElementById('github-update-modal');
    const updateInfoDiv = document.getElementById('github-update-info');

    if (updateInfoDiv) {
        updateInfoDiv.innerHTML = `
            <div class="update-info">
                <h3>GitHub Update Available</h3>
                <div class="version-info">
                    <p><strong>Current Version:</strong> ${updateInfo.current_version}</p>
                    <p><strong>Latest Version:</strong> ${updateInfo.latest_version}</p>
                    <p><strong>Release:</strong> ${updateInfo.release_info.tag_name}</p>
                    <p><strong>Published:</strong> ${new Date(updateInfo.release_info.published_at).toLocaleDateString()}</p>
                </div>
                <div class="release-notes">
                    <h4>Release Notes:</h4>
                    <div class="release-body">${updateInfo.release_info.body || 'No release notes available.'}</div>
                </div>
            </div>
        `;
    }

    modalElement.style.display = 'flex';
    modalElement.classList.add('active');
}

function closeGitHubUpdateModal() {
    const modal = document.getElementById('github-update-modal');
    if (modal) {
        modal.style.display = 'none';
        modal.classList.remove('active');
    }
}

function createGitHubUpdateModal() {
    const modalHTML = `
        <div id="github-update-modal" class="modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>GitHub Update</h2>
                    <button class="modal-close" id="close-github-update-modal">&times;</button>
                </div>
                <div id="github-update-info" class="modal-body">
                    <!-- Update info will be populated here -->
                    <div class="update-progress" id="github-update-progress" style="display:none; margin-top: 1rem;">
                        <div class="progress-bar">
                            <div class="progress-fill" id="github-progress-fill"></div>
                        </div>
                        <p class="progress-text" id="github-progress-text"></p>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn-secondary" id="cancel-github-update">Cancel</button>
                    <button class="btn-primary" id="download-github-update">Download & Install</button>
                </div>
            </div>
        </div>
    `;

    document.body.insertAdjacentHTML('beforeend', modalHTML);
    // Bind events for dynamically created elements
    const closeBtn = document.getElementById('close-github-update-modal');
    if (closeBtn) closeBtn.addEventListener('click', closeGitHubUpdateModal);
    const cancelBtn = document.getElementById('cancel-github-update');
    if (cancelBtn) cancelBtn.addEventListener('click', closeGitHubUpdateModal);
    const dlBtn = document.getElementById('download-github-update');
    if (dlBtn) dlBtn.addEventListener('click', downloadGitHubUpdate);
}

function showUpdateModal(updateInfo) {
    const modal = document.getElementById('update-modal');
    const updateInfoDiv = document.getElementById('update-info');

    updateInfoDiv.innerHTML = `
        <div class="update-version">Version ${updateInfo.version}</div>
        <div class="update-notes">${updateInfo.release_notes || 'No release notes available.'}</div>
        <p><strong>Published:</strong> ${new Date(updateInfo.published_at).toLocaleDateString()}</p>
        ${updateInfo.prerelease ? '<p><strong>Note:</strong> This is a pre-release version.</p>' : ''}
    `;

    // Reset progress UI
    const progressDiv = document.getElementById('update-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    if (progressDiv) progressDiv.style.display = 'none';
    if (progressFill) progressFill.style.width = '0%';
    if (progressText) progressText.textContent = '';
    isUpdateDownloading = false;

    currentUpdateInfo = updateInfo;
    modal.classList.add('active');
}

function closeUpdateModal() {
    const modal = document.getElementById('update-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    currentUpdateInfo = null;
}

async function downloadAndInstallUpdate() {
    if (!currentUpdateInfo) return;
    const progressDiv = document.getElementById('update-progress');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');

    // UI state
    progressDiv.style.display = 'block';
    progressText.textContent = 'Starting download...';
    isUpdateDownloading = true;

    // Start polling progress
    if (updatePollInterval) clearInterval(updatePollInterval);
    updatePollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/updates/progress');
            if (!res.ok) {
                let errText = `Failed to fetch progress (HTTP ${res.status})`;
                try {
                    const body = await res.json();
                    if (body && body.error) errText = body.error;
                } catch (_) {}
                throw new Error(errText);
            }

            const status = await res.json();
            lastUpdateStatus = status;
            const st = (status.status || '').toLowerCase();
            if (st === 'downloading') {
                const pct = Math.max(0, Math.min(100, status.progress || 0));
                progressFill.style.width = pct + '%';
                const downloadedMB = ((status.downloaded || 0) / (1024 * 1024)).toFixed(1);
                const totalMB = status.total ? ((status.total) / (1024 * 1024)).toFixed(1) : '...';
                progressText.textContent = `Downloading update... ${pct}% (${downloadedMB} / ${totalMB} MB)`;
            } else if (st === 'ready') {
                progressFill.style.width = '100%';
                progressText.textContent = 'Installing update...';
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                // Trigger install using the reported file name
                const fileName = status.update_file || `update_${currentUpdateInfo.version}.zip`;
                const installResponse = await fetch('/api/updates/install', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ update_file: fileName, backup_before_update: true })
                });
                let installResult = null;
                try { installResult = await installResponse.json(); } catch (_) {}
                if (!installResponse.ok) {
                    const msg = (installResult && installResult.error) ? installResult.error : 'Failed to install update';
                    throw new Error(msg);
                }
                if (!(installResult && installResult.success)) {
                    const msg = (installResult && installResult.error) ? installResult.error : 'Failed to install update';
                    throw new Error(msg);
                }
                showNotification('Update installed successfully! Please restart the application.', 'success');
                isUpdateDownloading = false;
                closeUpdateModal();
            } else if (st === 'failed') {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                isUpdateDownloading = false;
                showNotification('Update failed: ' + (status.error || 'Unknown error'), 'error');
            } else if (st === 'canceled') {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
                isUpdateDownloading = false;
                progressDiv.style.display = 'none';
                progressFill.style.width = '0%';
                progressText.textContent = '';
                showNotification('Update download canceled', 'info');
            }
        } catch (e) {
            console.error('Progress poll error:', e);
            if (updatePollInterval) {
                clearInterval(updatePollInterval);
                updatePollInterval = null;
            }
            isUpdateDownloading = false;
            showNotification('Update failed: ' + (e && e.message ? e.message : 'Progress polling failed'), 'error');
        }
    }, 800);

    // Kick off background download
    try {
        const response = await fetch('/api/updates/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentUpdateInfo)
        });
        let result = null;
        try { result = await response.json(); } catch (_) {}
        if (!response.ok && response.status !== 202) {
            const msg = (result && result.error) ? result.error : 'Failed to start download';
            throw new Error(msg);
        }
    } catch (e) {
        clearInterval(updatePollInterval);
        updatePollInterval = null;
        isUpdateDownloading = false;
        showNotification('Error starting update download: ' + (e && e.message ? e.message : 'Unknown error'), 'error');
    }
}

async function cancelOrCloseUpdateModal() {
    const progressDiv = document.getElementById('update-progress');
    const isVisible = progressDiv && progressDiv.style.display !== 'none';
    if (isVisible && isUpdateDownloading) {
        try {
            await fetch('/api/updates/cancel', { method: 'POST' });
        } catch (e) { /* ignore */ }
        if (updatePollInterval) { clearInterval(updatePollInterval); updatePollInterval = null; }
        isUpdateDownloading = false;
        progressDiv.style.display = 'none';
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = '';
        showNotification('Canceled update download', 'info');
        closeUpdateModal();
    } else {
        closeUpdateModal();
    }
}

async function createBackup() {
    try {
        // Ask user for backup location
        const backupLocation = await showBackupLocationDialog();
        if (!backupLocation) {
            return; // User cancelled
        }

        showNotification('Creating backup...', 'info');

        const response = await fetch('/api/backups/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                type: 'manual',
                location: backupLocation
            })
        });

        if (response.ok) {
            showNotification('Backup created successfully!', 'success');
        } else {
            throw new Error('Failed to create backup');
        }
    } catch (error) {
        console.error('Error creating backup:', error);
        showNotification('Error creating backup', 'error');
    }
}

function showBackupLocationDialog() {
    return new Promise((resolve) => {
        // Create a simple dialog for backup location
        const dialog = document.createElement('div');
        dialog.className = 'modal active';
        dialog.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>Choose Backup Location</h3>
                    <button class="modal-close" onclick="this.closest('.modal').remove()">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label for="backup-location">Backup Location:</label>
                        <input type="text" id="backup-location" placeholder="Enter folder path or leave empty for default" style="width: 100%;">
                    </div>
                    <div class="form-group">
                        <button class="btn-primary" onclick="confirmBackupLocation()">Create Backup</button>
                        <button class="btn-secondary" onclick="cancelBackupLocation()">Cancel</button>
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(dialog);

        // Global functions for the dialog
        window.confirmBackupLocation = () => {
            const location = document.getElementById('backup-location').value.trim();
            dialog.remove();
            resolve(location || null);
        };

        window.cancelBackupLocation = () => {
            dialog.remove();
            resolve(null);
        };

        // Focus the input
        setTimeout(() => {
            document.getElementById('backup-location').focus();
        }, 100);
    });
}

async function openBackupModal() {
    try {
        const response = await fetch('/api/backups');
        const result = await response.json();

        const backupList = document.getElementById('backup-list');
        backupList.innerHTML = '';

        if (result.backups.length === 0) {
            backupList.innerHTML = '<p>No backups available.</p>';
        } else {
            result.backups.forEach(backup => {
                const backupItem = document.createElement('div');
                backupItem.className = 'backup-item';
                backupItem.innerHTML = `
                    <div class="backup-info">
                        <div class="backup-name">${backup.name}</div>
                        <div class="backup-details">
                            Type: ${backup.type} |
                            Version: ${backup.version} |
                            Created: ${new Date(backup.created_at).toLocaleString()}
                        </div>
                    </div>
                    <div class="backup-actions">
                        <button class="backup-action backup-restore" onclick="restoreBackup('${backup.name}')">
                            Restore
                        </button>
                    </div>
                `;
                backupList.appendChild(backupItem);
            });
        }

        document.getElementById('backup-modal').classList.add('active');
    } catch (error) {
        console.error('Error loading backups:', error);
        showNotification('Error loading backups', 'error');
    }
}

function closeBackupModal() {
    document.getElementById('backup-modal').classList.remove('active');
}

async function restoreBackup(backupName) {
    if (!confirm(`Are you sure you want to restore backup "${backupName}"? This will replace your current data.`)) {
        return;
    }

    try {
        showNotification('Restoring backup...', 'info');

        const response = await fetch('/api/backups/restore', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ backup_name: backupName })
        });

        let result = null;
        try { result = await response.json(); } catch (_) {}

        if (!response.ok) {
            const msg = (result && result.error)
                ? result.error
                : `Failed to restore backup (HTTP ${response.status})`;
            throw new Error(msg);
        }

        if (!(result && result.success)) {
            const msg = (result && result.error)
                ? result.error
                : 'Failed to restore backup';
            throw new Error(msg);
        }

        showNotification('Backup restored successfully! Please refresh the page.', 'success');
        setTimeout(() => {
            window.location.reload();
        }, 2000);
    } catch (error) {
        console.error('Error restoring backup:', error);
        showNotification('Error restoring backup: ' + (error && error.message ? error.message : 'Unknown error'), 'error');
    }
}

async function updateUpdateSettings() {
    try {
        const autoCheckEl = document.getElementById('auto-update-check');
        const backupEl = document.getElementById('backup-before-update');
        const autoInstallEl = document.getElementById('auto-update-install');
        const channelEl = document.getElementById('update-channel');
        const intervalEl = document.getElementById('check-interval');

        const settings = {};

        if (autoCheckEl) settings.auto_check_enabled = !!autoCheckEl.checked;
        if (backupEl) settings.backup_before_update = !!backupEl.checked;
        if (autoInstallEl) settings.auto_install_enabled = !!autoInstallEl.checked;
        if (channelEl) settings.update_channel = channelEl.value;
        if (intervalEl) settings.check_interval_hours = parseInt(intervalEl.value);

        if (Object.keys(settings).length === 0) {
            return;
        }

        const response = await fetch('/api/updates/config', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            showNotification('Update settings saved!', 'success');
        } else {
            throw new Error('Failed to save settings');
        }
    } catch (error) {
        console.error('Error updating settings:', error);
        showNotification('Error saving update settings', 'error');
    }
}

async function loadUpdateSettings() {
    try {
        const response = await fetch('/api/updates/config');
        const config = await response.json();

        // Safely set values with null checks
        const autoCheckEl = document.getElementById('auto-update-check');
        const autoInstallEl = document.getElementById('auto-update-install');
        const backupEl = document.getElementById('backup-before-update');
        const channelEl = document.getElementById('update-channel');
        const intervalEl = document.getElementById('check-interval');

        if (autoCheckEl) {
            autoCheckEl.checked = (config.auto_check_enabled !== undefined)
                ? !!config.auto_check_enabled
                : !!config.auto_update;
        }
        if (autoInstallEl) {
            autoInstallEl.checked = (config.auto_install_enabled !== undefined)
                ? !!config.auto_install_enabled
                : !!config.auto_install;
        }
        if (backupEl) backupEl.checked = config.backup_before_update !== false;
        if (channelEl) channelEl.value = config.update_channel || config.channel || 'stable';
        if (intervalEl) intervalEl.value = config.check_interval_hours || config.check_interval || 24;
    } catch (error) {
        console.error('Error loading update settings:', error);
    }
}
