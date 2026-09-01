/* WesternFX IB Management — Settings Page */

const DEFAULT_URLS = {
    api2: 'https://script.google.com/macros/s/AKfycbxqYd0QanVEgAPNj5S4M6vQAtPavFEvhcsa6d_hgx6ip1-tZdLswLPgll17qeiqfuAx/exec',
    api3: 'https://script.google.com/macros/s/AKfycbx3av5WhEMS0MQVXXKxIdk3g6PcETmDw-Ty_sJYm3dstHD6hi2-_X_6J04O8EvQ5xw/exec'
};

let settingsData = {};

async function loadSettings() {
    settingsData = await getJSON('/api/settings');
    document.getElementById('api2-url').value = settingsData.api2_url || DEFAULT_URLS.api2;
    document.getElementById('api3-url').value = settingsData.api3_url || DEFAULT_URLS.api3;
    loadBackupStatus();
    loadDropboxStatus();
}

async function saveSettings() {
    const payload = {
        api2_url: document.getElementById('api2-url').value.trim(),
        api3_url: document.getElementById('api3-url').value.trim()
    };
    try {
        const result = await postJSON('/api/settings', payload);
        if (result.success) {
            showToast('Settings saved successfully', 'success');
        } else {
            showToast('Failed to save settings', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

function resetDefaults() {
    document.getElementById('api2-url').value = DEFAULT_URLS.api2;
    document.getElementById('api3-url').value = DEFAULT_URLS.api3;
    showToast('Defaults restored. Click Save to apply.', 'info');
}

async function testApi(apiKey) {
    const statusEl = document.getElementById(apiKey + '-status');
    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500"></i> Testing...';
    try {
        const result = await postJSON('/api/test-api', { api: apiKey });
        if (result.success) {
            statusEl.innerHTML = `<span class="text-green-600"><i class="fas fa-check-circle"></i> Connected (${result.records} records)</span>`;
        } else {
            statusEl.innerHTML = `<span class="text-red-600"><i class="fas fa-times-circle"></i> ${result.error}</span>`;
        }
    } catch (e) {
        statusEl.innerHTML = `<span class="text-red-600"><i class="fas fa-times-circle"></i> ${e.message}</span>`;
    }
}

// ── Dropbox OAuth Functions ──

async function loadDropboxStatus() {
    try {
        const result = await getJSON('/api/dropbox-status');
        const nameEl = document.getElementById('dropbox-user-name');
        const emailEl = document.getElementById('dropbox-user-email');
        const actionsEl = document.getElementById('dropbox-connect-actions');
        const authSection = document.getElementById('dropbox-auth-code-section');
        const actionsSection = document.getElementById('dropbox-actions-section');

        if (result.success && result.connected) {
            nameEl.textContent = result.name || 'Connected';
            emailEl.textContent = result.email || '';
            actionsEl.innerHTML = '<span class="text-green-600 text-sm font-medium"><i class="fas fa-check-circle mr-1"></i> Connected</span>';
            authSection.classList.add('hidden');
            actionsSection.classList.remove('hidden');
        } else {
            nameEl.textContent = 'Not connected';
            emailEl.textContent = result.error || 'Click Connect to authorize';
            actionsEl.innerHTML = '<button onclick="connectDropbox()" class="btn-primary btn-sm"><i class="fab fa-dropbox mr-1"></i>Connect Dropbox</button>';
            authSection.classList.add('hidden');
            actionsSection.classList.add('hidden');
        }
    } catch (e) {
        console.error('Failed to load Dropbox status:', e);
    }
}

async function connectDropbox() {
    const authSection = document.getElementById('dropbox-auth-code-section');
    const linkEl = document.getElementById('dropbox-auth-link');
    const statusEl = document.getElementById('dropbox-auth-status');

    statusEl.textContent = 'Generating authorization link...';
    authSection.classList.remove('hidden');

    try {
        const result = await getJSON('/api/dropbox-auth-url');
        if (result.success && result.auth_url) {
            linkEl.href = result.auth_url;
            linkEl.textContent = result.auth_url;
            statusEl.innerHTML = '<span class="text-blue-600"><i class="fas fa-external-link-alt mr-1"></i> Open the link in a new tab, authorize, then paste the code</span>';
        } else {
            statusEl.innerHTML = '<span class="text-red-600">Failed: ' + (result.error || '') + '</span>';
        }
    } catch (e) {
        statusEl.innerHTML = '<span class="text-red-600">' + e.message + '</span>';
    }
}

async function submitDropboxAuthCode() {
    const code = document.getElementById('dropbox-auth-code').value.trim();
    const statusEl = document.getElementById('dropbox-auth-status');

    if (!code) {
        showToast('Please paste the authorization code', 'warning');
        return;
    }

    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i> Exchanging code...';

    try {
        const result = await postJSON('/api/dropbox-auth-exchange', { code: code });
        if (result.success) {
            showToast('Dropbox connected!', 'success');
            loadDropboxStatus();
        } else {
            statusEl.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (result.error || 'Failed') + '</span>';
            showToast('Connection failed: ' + (result.error || ''), 'error');
        }
    } catch (e) {
        statusEl.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    }
}

async function disconnectDropbox() {
    if (!confirm('Disconnect Dropbox? You will need to re-authorize to back up again.')) {
        return;
    }
    try {
        const result = await postJSON('/api/dropbox-disconnect', {});
        if (result.success) {
            showToast('Dropbox disconnected', 'info');
            loadDropboxStatus();
        } else {
            showToast('Disconnect failed: ' + (result.error || ''), 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

// ── Cloud Backup Functions ──

async function loadBackupStatus() {
    try {
        const result = await getJSON('/api/backup-status');
        const infoEl = document.getElementById('last-backup-info');
        if (result.success && result.last_backup) {
            const date = new Date(result.last_backup.date).toLocaleString();
            infoEl.innerHTML = '<i class="fas fa-cloud text-blue-400 mr-1"></i> Last backup: <strong>' + date + '</strong> (' + (result.last_backup.filename || 'unknown') + ')';
        } else {
            infoEl.innerHTML = '<i class="fas fa-exclamation-circle text-amber-400 mr-1"></i> No backups yet. Click <strong>Backup Now</strong>.';
        }
    } catch (e) {
        console.error('Failed to load backup status:', e);
    }
}

async function loadBackupsList() {
    const container = document.getElementById('backups-list');
    if (!container) return;
    container.innerHTML = '<p class="text-sm text-gray-400 px-4 py-4 text-center"><i class="fas fa-spinner fa-spin mr-2"></i>Loading backups...</p>';

    try {
        const result = await getJSON('/api/backups');
        if (!result.success) {
            const msg = result.error || result.message || 'Failed to load backups';
            container.innerHTML = '<p class="text-sm text-red-500 px-4 py-4 text-center">' + msg + '</p>';
            return;
        }
        const backups = result.backups || [];
        if (backups.length === 0) {
            container.innerHTML = '<p class="text-sm text-gray-400 px-4 py-4 text-center">No backups found on Dropbox.</p>';
            return;
        }
        let html = '<table class="w-full text-sm"><thead><tr class="bg-gray-50"><th class="px-3 py-2 text-left">Filename</th><th class="px-3 py-2 text-left">Date</th><th class="px-3 py-2 text-right">Size</th><th class="px-3 py-2 text-right">Action</th></tr></thead><tbody>';
        backups.forEach(function(b) {
            const dateStr = b.created_at ? new Date(b.created_at).toLocaleString() : '—';
            const sizeMB = (b.size / (1024 * 1024)).toFixed(2);
            html += '<tr class="border-t"><td class="px-3 py-2 font-mono text-xs">' + b.name + '</td>';
            html += '<td class="px-3 py-2 text-gray-600">' + dateStr + '</td>';
            html += '<td class="px-3 py-2 text-right">' + sizeMB + ' MB</td>';
            html += '<td class="px-3 py-2 text-right"><button onclick="restoreBackup(\'' + b.name + '\')" class="text-blue-600 hover:text-blue-800 text-sm font-medium"><i class="fas fa-undo mr-1"></i>Restore</button></td></tr>';
        });
        html += '</tbody></table>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p class="text-sm text-red-500 px-4 py-4 text-center">' + e.message + '</p>';
    }
}

async function backupNow() {
    const btn = document.getElementById('backup-status');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i> Backing up...';
    try {
        const result = await postJSON('/api/backup-now', {});
        if (result.success) {
            btn.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> Backup saved: ' + result.filename + '</span>';
            showToast('Backup uploaded to Dropbox', 'success');
            loadBackupStatus();
            loadBackupsList();
        } else {
            btn.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + result.error + '</span>';
            showToast('Backup failed: ' + result.error, 'error');
        }
    } catch (e) {
        btn.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    }
}

async function restoreBackup(filename) {
    if (!confirm('This will REPLACE your current database with the backup "' + filename + '". Are you sure?')) {
        return;
    }
    try {
        const result = await postJSON('/api/restore', { filename: filename });
        if (result.success) {
            alert('Database restored successfully! The app will now reload.');
            window.location.reload();
        } else {
            showToast('Restore failed: ' + result.error, 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    }
}

async function loadSQLiteSyncData() {
    try {
        // Load snapshots
        const snaps = await getJSON('/api/snapshots');
        const snapSelect = document.getElementById('sqlite-snapshot-select');
        if (snapSelect) {
            snapSelect.innerHTML = '<option value="">-- Choose a saved snapshot --</option>';
            snaps.forEach(function(s) {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = (s.month_label || 'Snapshot') + ' — ' + (s.snapshot_date || '').slice(0, 10);
                snapSelect.appendChild(opt);
            });
        }
        // Load referrer options
        const refSelect = document.getElementById('sqlite-referrer-select');
        if (refSelect) {
            refSelect.innerHTML = '<option value="">-- Select Referrer --</option>';
            ['Tawhid Sir', 'Pradyut Sir'].forEach(function(r) {
                const opt = document.createElement('option');
                opt.value = r;
                opt.textContent = r;
                refSelect.appendChild(opt);
            });
        }
    } catch (e) {
        console.error('Failed to load SQLite sync data:', e);
    }
}

let sqliteSyncPreviewData = null;
let sqliteSyncTaskId = null;

async function previewSQLiteToApi2() {
    const snapshotId = document.getElementById('sqlite-snapshot-select').value;
    const referrer = document.getElementById('sqlite-referrer-select').value;
    const btn = document.getElementById('btn-sqlite-preview');
    const status = document.getElementById('sqlite-sync-status');

    if (!snapshotId || !referrer) {
        showToast('Please select both a snapshot and a referrer', 'warning');
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Analyzing...';
    status.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i> Comparing SQLite vs API 2...';

    try {
        const result = await postJSON('/api/sync-sqlite-to-api2', {
            snapshot_id: parseInt(snapshotId),
            referrer: referrer,
            dry_run: true
        });

        sqliteSyncPreviewData = result;

        if (!result.success) {
            status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (result.error || 'Failed') + '</span>';
            showToast(result.error || 'Preview failed', 'error');
            return;
        }

        // Show results container
        document.getElementById('sqlite-preview-results').classList.remove('hidden');

        // New clients
        const newClients = result.new_clients || [];
        const newSection = document.getElementById('sqlite-preview-new-section');
        const newBody = document.getElementById('sqlite-preview-new-body');
        document.getElementById('sqlite-preview-new-count').textContent = newClients.length;

        if (newClients.length > 0) {
            newSection.classList.remove('hidden');
            let html = '';
            newClients.forEach(function(c) {
                html += '<tr>';
                html += '<td class="px-3 py-2 font-mono text-xs">' + (c.account || '') + '</td>';
                html += '<td class="px-3 py-2">' + (c.fullName || '') + '</td>';
                html += '<td class="px-3 py-2 text-gray-500">' + (c.email || '') + '</td>';
                html += '<td class="px-3 py-2 text-right">' + (c.deposit !== null && c.deposit !== undefined ? c.deposit : '') + '</td>';
                html += '<td class="px-3 py-2 text-right">' + (c.balance !== null && c.balance !== undefined ? c.balance : '') + '</td>';
                html += '</tr>';
            });
            newBody.innerHTML = html;
        } else {
            newSection.classList.add('hidden');
        }

        // Changed clients
        const changedClients = result.changed_clients || [];
        const changedSection = document.getElementById('sqlite-preview-changed-section');
        const changedBody = document.getElementById('sqlite-preview-changed-body');
        document.getElementById('sqlite-preview-changed-count').textContent = changedClients.length;

        if (changedClients.length > 0) {
            changedSection.classList.remove('hidden');
            let html = '';
            changedClients.forEach(function(c) {
                const changes = c.field_changes || [];
                changes.forEach(function(fc, idx) {
                    html += '<tr class="' + (idx === 0 ? '' : 'border-t border-gray-100') + '">';
                    if (idx === 0) {
                        html += '<td class="px-3 py-2 font-mono text-xs" rowspan="' + changes.length + '">' + (c.account || '') + '</td>';
                        html += '<td class="px-3 py-2" rowspan="' + changes.length + '">' + (c.fullName || '') + '</td>';
                    }
                    html += '<td class="px-3 py-2 text-amber-700">' + (fc.field || '') + '</td>';
                    html += '<td class="px-3 py-2 text-right text-gray-500">' + (fc.old !== null && fc.old !== undefined ? fc.old : '—') + '</td>';
                    html += '<td class="px-3 py-2 text-right text-green-700 font-medium">' + (fc.new !== null && fc.new !== undefined ? fc.new : '—') + '</td>';
                    html += '</tr>';
                });
            });
            changedBody.innerHTML = html;
        } else {
            changedSection.classList.add('hidden');
        }

        // Show apply button if there are changes
        const applySection = document.getElementById('sqlite-apply-section');
        if (newClients.length > 0 || changedClients.length > 0) {
            applySection.classList.remove('hidden');
            status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> ' + newClients.length + ' new, ' + changedClients.length + ' to update</span>';
        } else {
            applySection.classList.add('hidden');
            status.innerHTML = '<span class="text-blue-600"><i class="fas fa-info-circle mr-1"></i> No changes detected — everything is up to date</span>';
        }

    } catch (e) {
        status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-eye mr-1"></i>Preview Changes';
    }
}

async function applySQLiteToApi2() {
    const snapshotId = document.getElementById('sqlite-snapshot-select').value;
    const referrer = document.getElementById('sqlite-referrer-select').value;
    const btn = document.getElementById('btn-sqlite-apply');
    const progress = document.getElementById('sqlite-progress');
    const bar = document.getElementById('sqlite-progress-bar');
    const text = document.getElementById('sqlite-progress-text');
    const status = document.getElementById('sqlite-sync-status');

    if (!snapshotId || !referrer) {
        showToast('Please select both a snapshot and a referrer', 'warning');
        return;
    }

    if (!confirm('This will push ' + (sqliteSyncPreviewData?.new_count || 0) + ' new clients and update ' + (sqliteSyncPreviewData?.changed_count || 0) + ' existing clients in API 2. Continue?')) {
        return;
    }

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-1"></i>Applying...';
    progress.classList.remove('hidden');
    bar.style.width = '0%';
    text.textContent = 'Starting sync...';

    try {
        const result = await postJSON('/api/sync-sqlite-to-api2', {
            snapshot_id: parseInt(snapshotId),
            referrer: referrer,
            dry_run: false
        });

        if (!result.success) {
            status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (result.error || 'Failed') + '</span>';
            showToast(result.error || 'Sync failed', 'error');
            return;
        }

        sqliteSyncTaskId = result.task_id;
        text.textContent = 'Sync started (' + result.total + ' operations)...';

        // Poll progress
        pollSQLiteSyncProgress(result.task_id, result.total);

    } catch (e) {
        status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-cloud-upload-alt mr-1"></i>Apply Changes to API 2';
    }
}

async function pollSQLiteSyncProgress(taskId, total) {
    const bar = document.getElementById('sqlite-progress-bar');
    const text = document.getElementById('sqlite-progress-text');
    const status = document.getElementById('sqlite-sync-status');
    const btn = document.getElementById('btn-sqlite-apply');

    let completed = false;
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes at 1s intervals

    while (!completed && attempts < maxAttempts) {
        attempts++;
        try {
            const result = await getJSON('/api/sync-sqlite-to-api2/progress/' + taskId);
            if (result.success) {
                const done = result.done || 0;
                const pct = total > 0 ? Math.round((done / total) * 100) : 0;
                bar.style.width = pct + '%';
                text.textContent = done + ' / ' + total + ' completed';

                if (result.status === 'done') {
                    completed = true;
                    status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> Sync complete!</span>';
                    showToast('SQLite → API 2 sync completed successfully', 'success');
                    btn.innerHTML = '<i class="fas fa-check mr-1"></i>Done';
                    setTimeout(function() {
                        btn.disabled = false;
                        btn.innerHTML = '<i class="fas fa-cloud-upload-alt mr-1"></i>Apply Changes to API 2';
                        document.getElementById('sqlite-apply-section').classList.add('hidden');
                    }, 3000);
                } else if (result.status === 'error') {
                    completed = true;
                    status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> Sync failed: ' + (result.error || 'Unknown error') + '</span>';
                    showToast('Sync failed: ' + (result.error || ''), 'error');
                    btn.disabled = false;
                    btn.innerHTML = '<i class="fas fa-cloud-upload-alt mr-1"></i>Apply Changes to API 2';
                }
            }
        } catch (e) {
            console.error('Progress poll error:', e);
        }
        if (!completed) {
            await new Promise(function(r) { setTimeout(r, 1000); });
        }
    }

    if (!completed) {
        status.innerHTML = '<span class="text-amber-600"><i class="fas fa-exclamation-triangle mr-1"></i> Sync timed out. Check API 2 manually.</span>';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-cloud-upload-alt mr-1"></i>Apply Changes to API 2';
    }
}

// Load on page ready
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    loadLocalBackupMonths();
    loadSQLiteSyncData();
});

// ── Local Backup Functions ──

async function loadLocalBackupMonths() {
    const select = document.getElementById('local-backup-month');
    if (!select) return;
    try {
        const result = await getJSON('/api/snapshots');
        const months = [...new Set(result.map(s => s.month_label).filter(Boolean))].sort().reverse();
        select.innerHTML = '<option value="">-- All Data (Full DB) --</option>';
        months.forEach(function(m) {
            const opt = document.createElement('option');
            opt.value = m;
            opt.textContent = m;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load months:', e);
    }
}

async function downloadLocalBackup() {
    const month = document.getElementById('local-backup-month').value;
    const statusEl = document.getElementById('local-backup-status');
    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Preparing backup...';
    try {
        const params = month ? '?month=' + encodeURIComponent(month) : '';
        const response = await fetch('/api/local-backup' + params);
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const filename = response.headers.get('content-disposition')?.match(/filename="(.+)"/)[1] || 'westernfx_backup.sql';
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        statusEl.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> Downloaded</span>';
        showToast('SQL backup downloaded', 'success');
    } catch (e) {
        statusEl.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Backup failed: ' + e.message, 'error');
    }
}

async function uploadSQLFile() {
    const fileInput = document.getElementById('sql-upload-file');
    const statusEl = document.getElementById('sql-upload-status');
    const file = fileInput?.files?.[0];
    if (!file) {
        showToast('Please select a SQL file', 'warning');
        return;
    }
    if (!confirm('WARNING: This will replace your entire database with the contents of this SQL file. The current database will be backed up locally first. Continue?')) {
        return;
    }
    statusEl.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Uploading...';
    try {
        const formData = new FormData();
        formData.append('sql_file', file);
        const response = await fetch('/api/restore-sql', {
            method: 'POST',
            body: formData
        });
        const result = await response.json();
        if (result.success) {
            statusEl.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> Restored</span>';
            showToast('Database restored. Reloading app...', 'success');
            setTimeout(function() { window.location.reload(); }, 2000);
        } else {
            statusEl.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (result.error || 'Restore failed') + '</span>';
            showToast('Restore failed: ' + (result.error || 'Unknown error'), 'error');
        }
    } catch (e) {
        statusEl.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Restore failed: ' + e.message, 'error');
    }
}
