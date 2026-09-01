/* WesternFX IB Management — Settings Page */

const DEFAULT_URLS = {
    api1: 'https://script.google.com/macros/s/AKfycbx2m-4xxpU3HiXl43tTvCti0wiUkclWiQkVG-hlL841xhjsYkRsSjHq_bY2eAvjZWxf/exec',
    api2: 'https://script.google.com/macros/s/AKfycbxqYd0QanVEgAPNj5S4M6vQAtPavFEvhcsa6d_hgx6ip1-tZdLswLPgll17qeiqfuAx/exec',
    api3: 'https://script.google.com/macros/s/AKfycbx3av5WhEMS0MQVXXKxIdk3g6PcETmDw-Ty_sJYm3dstHD6hi2-_X_6J04O8EvQ5xw/exec'
};

let settingsData = {};

async function loadSettings() {
    settingsData = await getJSON('/api/settings');
    document.getElementById('api1-url').value = settingsData.api1_url || DEFAULT_URLS.api1;
    document.getElementById('api2-url').value = settingsData.api2_url || DEFAULT_URLS.api2;
    document.getElementById('api3-url').value = settingsData.api3_url || DEFAULT_URLS.api3;
    loadBackupStatus();
    loadDropboxStatus();
}

async function saveSettings() {
    const payload = {
        api1_url: document.getElementById('api1-url').value.trim(),
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
    document.getElementById('api1-url').value = DEFAULT_URLS.api1;
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
            container.innerHTML = '<p class="text-sm text-red-500 px-4 py-4 text-center">' + (result.error || 'Failed to load backups') + '</p>';
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

// Load on page ready
document.addEventListener('DOMContentLoaded', function() {
    loadSettings();
    loadLocalBackupMonths();
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
