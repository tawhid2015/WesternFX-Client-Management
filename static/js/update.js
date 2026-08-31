/* WesternFX IB Management — Update Monthly Sheet Page (v2: + delete month)
   Self-contained: no external JS dependencies */

// ── Inline helpers ──
async function getJSON(url) {
    const urlWithReferrer = typeof buildUrlWithReferrer === 'function' ? buildUrlWithReferrer(url) : url;
    const r = await fetch(urlWithReferrer);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}

async function postJSON(url, data) {
    const urlWithReferrer = typeof buildUrlWithReferrer === 'function' ? buildUrlWithReferrer(url) : url;
    const r = await fetch(urlWithReferrer, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}

async function deleteJSON(url) {
    const urlWithReferrer = typeof buildUrlWithReferrer === 'function' ? buildUrlWithReferrer(url) : url;
    const r = await fetch(urlWithReferrer, { method: 'DELETE' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
}

function showToast(message, type) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    const colors = {
        info: 'bg-blue-600',
        success: 'bg-green-600',
        error: 'bg-red-600',
        warning: 'bg-yellow-600'
    };
    toast.className = `${colors[type] || colors.info} text-white px-4 py-3 rounded-lg shadow-lg flex items-center gap-2`;
    toast.innerHTML = `<span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ── State ──
let fetchedRecords = [];
let fetchedCount = 0;
let htmlParsedRecords = [];
let htmlParsedCount = 0;
let dataSource = 'api'; // 'api' or 'html'

// ── Parse HTML Upload ──
async function parseHtmlFile() {
    const fileInput = document.getElementById('html-file');
    const btn = document.getElementById('btn-parse-html');
    const status = document.getElementById('html-parse-status');

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        showToast('Please select an HTML file first', 'warning');
        return;
    }

    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('html_file', file);

    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Parsing...';
    }
    if (status) status.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i> Parsing HTML...';

    try {
        const r = await fetch('/api/parse-html', {
            method: 'POST',
            body: formData
        });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();

        if (data.success) {
            htmlParsedRecords = data.traders || [];
            htmlParsedCount = data.summary ? data.summary.total_traders : 0;
            dataSource = 'html';

            // Map to match API format for preview
            fetchedRecords = htmlParsedRecords.map(function(t) {
                return {
                    fullName: t.full_name,
                    email: t.email,
                    account: t.account_number,
                    status: t.balance > 0 ? 'Active' : 'Inactive',
                    deposit: t.deposit,
                    balance: t.balance,
                    equity: t.equity,
                    pnl: t.pnl,
                    commission: t.commission,
                    commissionTotal: t.commission_total,
                    referredBy: 'Tawhid Sir'  // Default since all HTML data is from Tawhid
                };
            });
            fetchedCount = htmlParsedCount;

            if (status) status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> ' + htmlParsedCount + ' traders parsed</span>';
            showPreview(fetchedRecords);
            document.getElementById('preview-section').classList.remove('hidden');
            // Note: sync section is API-only, keep hidden for HTML uploads
            showToast('Parsed ' + htmlParsedCount + ' traders from HTML', 'success');
        } else {
            if (status) status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (data.error || 'Failed') + '</span>';
            showToast(data.error || 'Failed to parse HTML', 'error');
        }
    } catch (e) {
        if (status) status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-file-code mr-2"></i>Parse & Preview';
        }
    }
}

// ── Fetch from API 3 ──
async function fetchApi3() {
    const btn = document.getElementById('btn-fetch');
    const status = document.getElementById('fetch-status');
    if (!btn) return;
    btn.disabled = true;
    status.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i> Fetching...';

    try {
        const data = await postJSON('/api/fetch-api3', {});
        if (data.success) {
            fetchedRecords = data.records || [];
            fetchedCount = data.count || 0;
            status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> ' + fetchedCount + ' records fetched</span>';
            showPreview(fetchedRecords);
            loadReferrers();
            document.getElementById('preview-section').classList.remove('hidden');
            document.getElementById('sync-section').classList.remove('hidden');
            showToast('Fetched ' + fetchedCount + ' records from API 3', 'success');
        } else {
            status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (data.error || 'Failed') + '</span>';
            showToast(data.error || 'Failed to fetch', 'error');
        }
    } catch (e) {
        status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

// ── Show preview table ──
function showPreview(records) {
    const countEl = document.getElementById('preview-count');
    const thead = document.getElementById('preview-head');
    const tbody = document.getElementById('preview-body');

    if (countEl) countEl.textContent = '' + records.length;

    if (records.length > 0) {
        const keys = Object.keys(records[0]);
        let h = '<tr>';
        keys.forEach(function(k) { h += '<th class="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase bg-gray-50">' + k + '</th>'; });
        h += '</tr>';
        if (thead) thead.innerHTML = h;

        let b = '';
        const display = records.slice(0, 10);
        display.forEach(function(row) {
            b += '<tr>';
            Object.values(row).forEach(function(v) {
                b += '<td class="px-4 py-3 text-sm text-gray-700 border-b">' + (v !== null && v !== undefined ? v : '') + '</td>';
            });
            b += '</tr>';
        });
        if (records.length > 10) {
            b += '<tr><td colspan="' + keys.length + '" class="px-4 py-3 text-center text-gray-400">... and ' + (records.length - 10) + ' more rows</td></tr>';
        }
        if (tbody) tbody.innerHTML = b;
    }
}

// ── Load referrer options ──
async function loadReferrers() {
    try {
        const data = await getJSON('/api/referrers');
        const select = document.getElementById('referrer-select');
        if (!select) return;
        select.innerHTML = '<option value="">Select Referred by...</option>';
        data.forEach(function(r) {
            const opt = document.createElement('option');
            opt.value = r;
            opt.textContent = r;
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load referrers:', e);
    }
}

// ── Save snapshot ──
async function saveSnapshot() {
    const btn = document.getElementById('btn-save');
    const label = document.getElementById('month-label').value.trim();
    const monthLabel = label || new Date().toISOString().slice(0, 10);
    if (!btn) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Saving...';

    try {
        const result = await postJSON('/api/save-snapshot', {
            month_label: monthLabel,
            records: fetchedRecords
        });

        const resultSection = document.getElementById('result-section');
        const resultContent = document.getElementById('result-content');
        if (resultSection) resultSection.classList.remove('hidden');

        if (result && result.success) {
            if (resultContent) resultContent.innerHTML =
                '<div class="bg-green-50 border border-green-200 rounded-lg p-4">' +
                '<p class="text-green-800 font-medium"><i class="fas fa-check-circle mr-2"></i>Snapshot saved successfully!</p>' +
                '<ul class="mt-2 text-sm text-green-700 space-y-1">' +
                '<li>Month: <strong>' + result.month_label + '</strong></li>' +
                '<li>Records saved: <strong>' + result.records_saved + '</strong></li>' +
                '<li>New clients: <strong>' + (result.new_clients || 0) + '</strong></li>' +
                '<li>Removed clients: <strong>' + (result.removed_clients || 0) + '</strong></li>' +
                '<li>Changed clients: <strong>' + (result.changed_clients || 0) + '</strong></li>' +
                '</ul></div>';
            showToast('Snapshot saved! Reload dashboard to see updated data.', 'success');
            loadDeleteMonths();
        } else {
            if (resultContent) resultContent.innerHTML =
                '<div class="bg-red-50 border border-red-200 rounded-lg p-4">' +
                '<p class="text-red-800"><i class="fas fa-times-circle mr-2"></i>' + (result.error || 'Failed to save snapshot') + '</p>' +
                '</div>';
            showToast(result.error || 'Failed to save', 'error');
        }
    } catch (e) {
        showToast('Error: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-save mr-2"></i>Save as New Snapshot';
    }
}

// ── Sync API 2 ──
async function syncApi2() {
    const select = document.getElementById('referrer-select');
    const referrer = select ? select.value : '';
    const btn = document.getElementById('btn-sync');
    const status = document.getElementById('sync-status');

    if (!referrer) {
        showToast('Please select a referrer first', 'warning');
        return;
    }

    if (btn) btn.disabled = true;
    if (status) status.innerHTML = '<i class="fas fa-spinner fa-spin text-blue-500 mr-1"></i> Syncing...';

    try {
        const result = await postJSON('/api/sync-api2', { referrer: referrer });
        if (result && result.success) {
            if (status) status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> Updated ' + (result.updated || 0) + ' records</span>';
            showToast('API 2 sync completed', 'success');
        } else {
            if (status) status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (result.error || 'Sync failed') + '</span>';
            showToast(result.error || 'Sync failed', 'error');
        }
    } catch (e) {
        if (status) status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ── Load delete-month dropdown ──
async function loadDeleteMonths() {
    try {
        const data = await getJSON('/api/snapshots');
        const select = document.getElementById('delete-month-select');
        if (!select) return;
        select.innerHTML = '<option value="">Select month to delete...</option>';
        data.reverse().forEach(function(s) {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = (s.month_label || s.week_label || '') + ' — ' + (s.snapshot_date || '').slice(0, 10);
            select.appendChild(opt);
        });
    } catch (e) {
        console.error('Failed to load snapshot list:', e);
    }
}

// ── Delete month ──
async function deleteMonth() {
    const select = document.getElementById('delete-month-select');
    const btn = document.getElementById('btn-delete');
    const status = document.getElementById('delete-status');
    const id = select ? select.value : '';

    if (!id) {
        showToast('Please select a month to delete', 'warning');
        return;
    }

    const label = select.options[select.selectedIndex].textContent;
    if (!confirm('Delete "' + label + '" permanently?\n\nThis will remove all client records for this month.\nThis cannot be undone.')) {
        return;
    }

    if (btn) btn.disabled = true;
    if (status) status.innerHTML = '<i class="fas fa-spinner fa-spin text-red-500 mr-1"></i> Deleting...';

    try {
        const result = await deleteJSON('/api/snapshot/' + id);
        if (result && result.success) {
            if (status) status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> Deleted</span>';
            showToast('Monthly snapshot deleted', 'success');
            loadDeleteMonths();
        } else {
            if (status) status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + (result.error || 'Delete failed') + '</span>';
            showToast(result.error || 'Delete failed', 'error');
        }
    } catch (e) {
        if (status) status.innerHTML = '<span class="text-red-600"><i class="fas fa-times-circle mr-1"></i> ' + e.message + '</span>';
        showToast('Error: ' + e.message, 'error');
    } finally {
        if (btn) btn.disabled = false;
    }
}

// ── Auto-fill month label on load ──
document.addEventListener('DOMContentLoaded', function() {
    const el = document.getElementById('month-label');
    if (el && !el.value) {
        el.value = new Date().toISOString().slice(0, 7);
    }
    loadDeleteMonths();
});
