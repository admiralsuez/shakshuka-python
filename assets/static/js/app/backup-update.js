// Update and Backup Management Functions
let currentUpdateInfo = null;
let updatePollInterval = null;
let isUpdateDownloading = false;
let lastUpdateStatus = null;

// Unified update check handler for the Settings "Check for Updates" button.
// This now delegates to the GitHub-based check so that any newer version
// published on GitHub will surface via the GitHub update modal.
async function checkForUpdates() {
    return checkGitHubUpdate();
}

async function checkGitHubUpdate() {
    try {
        const branchElement = document.getElementById('github-branch');
        const branch = branchElement ? branchElement.value : 'main';
        showNotification('Checking GitHub for updates...', 'info');

        const response = await fetch('/api/github/check-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ branch: branch })
        });

        const result = await response.json();

        if (result.update_available) {
            showGitHubUpdateModal(result);
            showNotification('GitHub update available!', 'success');
        } else {
            showNotification(`You are up to date! (${result.current_version})`, 'success');
        }
    } catch (error) {
        console.error('Error checking GitHub update:', error);
        showNotification('Error checking GitHub for updates', 'error');
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

        const response = await fetch('/api/github/check-update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ branch })
        });

        if (!response.ok) {
            return;
        }

        const result = await response.json();
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

        // Simple front-end progress simulation while the download request runs.
        // This does not reflect exact bytes, but gives visual feedback.
        let fakePct = 0;
        let progressTimer = null;
        if (progressDiv && progressFill && progressText) {
            progressTimer = setInterval(() => {
                if (fakePct < 95) {
                    fakePct += 3;
                    progressFill.style.width = Math.min(fakePct, 95) + '%';
                    progressText.textContent = 'Downloading update...';
                }
            }, 500);
        }

        const response = await fetch('/api/github/download-update', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ branch: branch })
        });

        const result = await response.json();

        if (progressTimer) {
            clearInterval(progressTimer);
            progressTimer = null;
        }

        if (result.success) {
            const path = result.installer_path || 'the downloaded installer file';
            if (progressDiv && progressFill && progressText) {
                progressFill.style.width = '100%';
                progressText.textContent = 'Download complete.';
            }
            // Short success snack about the update itself
            showNotification('Update installer downloaded. Please close Shakshuka and run the installer to finish updating.', 'success');

            // Persistent, clickable toast that shows where the file went and
            // lets the user open the folder directly.
            const friendlyPath = path;
            const safeMessage = `Download finished to "${friendlyPath}" (click to open folder)`;
            showNotification(safeMessage, 'info', {
                persistent: true,
                onClick: () => {
                    try {
                        const payload = encodeURIComponent(friendlyPath);
                        window.location.href = `shakshuka-open-folder://${payload}`;
                    } catch (e) {
                        console.error('Failed to trigger folder open for installer path', e);
                    }
                }
            });

            // Close any open modals
            try { closeUpdateModal(); } catch (_) {}
            try { closeGitHubUpdateModal(); } catch (_) {}
        } else {
            if (progressDiv && progressText) {
                progressText.textContent = 'Download failed.';
            }
            showNotification(`Update failed: ${result.error}`, 'error');
        }
    } catch (error) {
        console.error('Error downloading GitHub update:', error);
        showNotification('Error downloading update from GitHub', 'error');
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
                if (!installResponse.ok) throw new Error('Failed to install update');
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
        }
    }, 800);

    // Kick off background download
    try {
        const response = await fetch('/api/updates/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentUpdateInfo)
        });
        if (!response.ok && response.status !== 202) {
            throw new Error('Failed to start download');
        }
    } catch (e) {
        clearInterval(updatePollInterval);
        updatePollInterval = null;
        isUpdateDownloading = false;
        showNotification('Error starting update download', 'error');
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

        if (response.ok) {
            showNotification('Backup restored successfully! Please refresh the page.', 'success');
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        } else {
            throw new Error('Failed to restore backup');
        }
    } catch (error) {
        console.error('Error restoring backup:', error);
        showNotification('Error restoring backup', 'error');
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
