/* WesternFX IB Management — Sync API 2 with API 3
   Clean preview: New Data + Updating Data only
   Fields: Account Id, Student Name, Mail Id, Deposit, Current Balance, Active/Inactive
   Preview is read-only. Sync Now applies changes.
*/

async function getJSON(url) {
    const urlWithReferrer = typeof buildUrlWithReferrer === 'function' ? buildUrlWithReferrer(url) : url;
    const r = await fetch(urlWithReferrer);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
}

async function postJSON(url, data) {
    const urlWithReferrer = typeof buildUrlWithReferrer === 'function' ? buildUrlWithReferrer(url) : url;
    const r = await fetch(urlWithReferrer, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
}

function fmtCurrency(n) {
    if (n === undefined || n === null || n === '') return '—';
    const num = typeof n === 'string' ? parseFloat(n) : n;
    if (isNaN(num)) return '—';
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

let previewData = null;
let pollInterval = null;

// ── Init ──
document.addEventListener('DOMContentLoaded', loadReferrers);

async function loadReferrers() {
    try {
        const data = await getJSON('/api/referrers');
        const select = document.getElementById('sync-referrer-select');
        if (!select) return;
        select.innerHTML = '<option value="">-- Select Referrer --</option>';
        (data || []).forEach(function(r) {
            const opt = document.createElement('option');
            opt.value = r;
            opt.textContent = r;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load referrers:', e);
    }
}

function showLoading(show) {
    const el = document.getElementById('sync-loading');
    if (!el) return;
    if (show) el.classList.remove('hidden');
    else el.classList.add('hidden');
}

function setBtnState(btnId, loading, text) {
    const btn = document.getElementById(btnId);
    if (!btn) return;
    btn.disabled = loading;
    btn.innerHTML = loading ? '<i class="fas fa-spinner fa-spin mr-1"></i> ' + (text || 'Processing...') : text;
}

// ── Preview Sync ──
async function previewSync() {
    const select = document.getElementById('sync-referrer-select');
    if (!select) return;
    const referrer = select.value;
    if (!referrer) {
        alert('Please select a referrer.');
        return;
    }

    showLoading(true);
    setBtnState('btn-preview', true, 'Analyzing...');
    document.getElementById('preview-section').classList.add('hidden');
    document.getElementById('sync-done').classList.add('hidden');
    hideProgress();

    try {
        const data = await postJSON('/api/sync-api2', { referrer: referrer, dry_run: true });
        previewData = data;
        showLoading(false);
        setBtnState('btn-preview', false, 'Preview Changes');

        if (!data.success) {
            alert('Preview failed: ' + (data.error || 'Unknown error'));
            return;
        }

        renderPreview(data);
        document.getElementById('preview-section').classList.remove('hidden');

    } catch (e) {
        showLoading(false);
        setBtnState('btn-preview', false, 'Preview Changes');
        alert('Error: ' + e.message);
    }
}

function renderPreview(data) {
    const newClients = data.new_clients || [];
    const changedClients = data.changed_clients || [];

    // Summary line
    const summaryText = document.getElementById('summary-text');
    if (newClients.length === 0 && changedClients.length === 0) {
        summaryText.textContent = 'Everything is up to date for ' + (data.referrer || 'this referrer') + '.';
    } else {
        const parts = [];
        if (newClients.length > 0) parts.push(newClients.length + ' new client' + (newClients.length > 1 ? 's' : ''));
        if (changedClients.length > 0) parts.push(changedClients.length + ' update' + (changedClients.length > 1 ? 's' : ''));
        summaryText.textContent = 'Found ' + parts.join(' and ') + ' for ' + (data.referrer || 'this referrer') + '.';
    }

    // NEW DATA
    const newSection = document.getElementById('new-data-section');
    const newBody = document.getElementById('new-data-body');
    const newCount = document.getElementById('new-count');
    if (newClients.length > 0) {
        newSection.classList.remove('hidden');
        newCount.textContent = '(' + newClients.length + ')';
        let html = '';
        newClients.forEach(function(c) {
            const activeInactive = _balanceToStatus(c.balance);
            html += '<tr class="hover:bg-purple-50">';
            html += '<td class="px-3 py-2 border-b font-mono text-gray-600">' + _esc(c.account) + '</td>';
            html += '<td class="px-3 py-2 border-b text-gray-800 font-medium">' + _esc(c.fullName) + '</td>';
            html += '<td class="px-3 py-2 border-b text-gray-600">' + _esc(c.email) + '</td>';
            html += '<td class="px-3 py-2 border-b text-right text-gray-600">' + fmtCurrency(c.deposit).replace('$', '') + '</td>';
            html += '<td class="px-3 py-2 border-b text-right text-gray-600">' + fmtCurrency(c.balance).replace('$', '') + '</td>';
            html += '<td class="px-3 py-2 border-b text-center">' + _statusBadge(activeInactive) + '</td>';
            html += '</tr>';
        });
        newBody.innerHTML = html;
    } else {
        newSection.classList.add('hidden');
    }

    // UPDATING DATA
    const updatingSection = document.getElementById('updating-data-section');
    const updatingBody = document.getElementById('updating-data-body');
    const updatingCount = document.getElementById('updating-count');
    if (changedClients.length > 0) {
        updatingSection.classList.remove('hidden');
        updatingCount.textContent = '(' + changedClients.length + ')';
        let html = '';
        changedClients.forEach(function(c) {
            const changes = c.field_changes || [];
            let changesHtml = '';
            changes.forEach(function(ch, idx) {
                if (idx > 0) changesHtml += '<br>';
                changesHtml += '<span class="text-xs text-gray-500">' + _esc(ch.field) + ':</span> ';
                changesHtml += '<span class="text-xs text-red-600 line-through">' + _esc(String(ch.old !== undefined && ch.old !== '' ? ch.old : '—')) + '</span> ';
                changesHtml += '<span class="text-xs text-gray-400">→</span> ';
                changesHtml += '<span class="text-xs text-green-600 font-medium">' + _esc(String(ch.new !== undefined && ch.new !== '' ? ch.new : '—')) + '</span>';
            });
            html += '<tr class="hover:bg-yellow-50">';
            html += '<td class="px-3 py-2 border-b font-mono text-gray-600">' + _esc(c.account) + '</td>';
            html += '<td class="px-3 py-2 border-b text-gray-800">' + _esc(c.fullName) + '</td>';
            html += '<td class="px-3 py-2 border-b text-gray-600">' + (changesHtml || '<span class="text-xs text-gray-400">No changes</span>') + '</td>';
            html += '</tr>';
        });
        updatingBody.innerHTML = html;
    } else {
        updatingSection.classList.add('hidden');
    }

    // NO CHANGES
    const noChanges = document.getElementById('no-changes');
    const btnSync = document.getElementById('btn-sync');
    if (newClients.length === 0 && changedClients.length === 0) {
        noChanges.classList.remove('hidden');
        btnSync.disabled = true;
        btnSync.textContent = 'Up to Date';
    } else {
        noChanges.classList.add('hidden');
        btnSync.disabled = false;
        const total = newClients.length + changedClients.length;
        btnSync.innerHTML = '<i class="fas fa-paper-plane mr-1"></i> Sync Now — ' + total + ' update' + (total > 1 ? 's' : '');
    }
}

function _balanceToStatus(balance) {
    const b = parseFloat(balance);
    if (isNaN(b)) return 'Inactive';
    return b > 0 ? 'Active' : 'Inactive';
}

function _statusBadge(status) {
    const s = (status || '').toLowerCase();
    if (s === 'active') {
        return '<span class="inline-block bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded font-medium">Active</span>';
    }
    return '<span class="inline-block bg-red-100 text-red-700 text-xs px-2 py-0.5 rounded font-medium">Inactive</span>';
}

function _esc(str) {
    if (str === undefined || str === null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

// ── Progress UI ──
function showProgress() {
    const el = document.getElementById('sync-progress');
    if (el) el.classList.remove('hidden');
}

function hideProgress() {
    const el = document.getElementById('sync-progress');
    if (el) el.classList.add('hidden');
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

function updateProgress(done, total) {
    const pct = total > 0 ? Math.round((done / total) * 100) : 0;
    const bar = document.getElementById('progress-bar');
    const text = document.getElementById('progress-text');
    if (bar) bar.style.width = pct + '%';
    if (text) text.textContent = done + ' / ' + total;
}

// ── Execute Sync ──
async function executeSync() {
    if (!previewData || !previewData.referrer) return;

    const newCount = (previewData.new_clients || []).length;
    const changedCount = (previewData.changed_clients || []).length;
    const totalCount = newCount + changedCount;

    if (totalCount === 0) {
        alert('Nothing to sync.');
        return;
    }

    let msg = 'This will:';
    if (newCount > 0) msg += '\n• Add ' + newCount + ' new client(s) to API 2';
    if (changedCount > 0) msg += '\n• Update ' + changedCount + ' existing client(s) in API 2';
    msg += '\n\nAre you sure?';

    if (!confirm(msg)) return;

    showLoading(true);
    setBtnState('btn-sync', true, 'Syncing...');
    hideProgress();

    try {
        const data = await postJSON('/api/sync-api2', { referrer: previewData.referrer, dry_run: false });
        showLoading(false);

        if (!data.success) {
            setBtnState('btn-sync', false, '<i class="fas fa-paper-plane mr-1"></i> Sync Now');
            alert('Sync failed: ' + (data.error || 'Unknown error'));
            return;
        }

        if (data.task_id) {
            showProgress();
            updateProgress(0, data.total);
            startPolling(data.task_id);
        } else {
            setBtnState('btn-sync', false, '<i class="fas fa-paper-plane mr-1"></i> Sync Now');
            onSyncComplete();
        }

    } catch (e) {
        showLoading(false);
        setBtnState('btn-sync', false, '<i class="fas fa-paper-plane mr-1"></i> Sync Now');
        hideProgress();
        alert('Error: ' + e.message);
    }
}

function startPolling(taskId) {
    if (pollInterval) clearInterval(pollInterval);

    pollInterval = setInterval(async function() {
        try {
            const data = await getJSON('/api/sync-api2/progress/' + taskId);
            if (!data) return;

            updateProgress(data.done || 0, data.total || 1);

            if (data.status === 'done') {
                clearInterval(pollInterval);
                pollInterval = null;
                hideProgress();
                setBtnState('btn-sync', false, '<i class="fas fa-paper-plane mr-1"></i> Sync Now');
                onSyncComplete();
            } else if (data.status === 'error') {
                clearInterval(pollInterval);
                pollInterval = null;
                hideProgress();
                setBtnState('btn-sync', false, '<i class="fas fa-paper-plane mr-1"></i> Sync Now');
                alert('Sync failed: ' + (data.error || 'Unknown error'));
            }
        } catch (e) {
            console.error('Poll error:', e);
        }
    }, 2000);
}

function onSyncComplete() {
    document.getElementById('sync-done').classList.remove('hidden');
    // Refresh preview after a moment
    setTimeout(function() {
        previewSync();
    }, 1500);
}
