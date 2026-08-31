/* WesternFX IB Management — All Clients Page (v2: Monthly)
   Self-contained: includes all helpers inline */

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
    if (n === undefined || n === null) return '$0.00';
    const num = typeof n === 'string' ? parseFloat(n) : n;
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtNumber(n) {
    if (n === undefined || n === null) return '0';
    return Number(n).toLocaleString('en-US');
}

// ── State ──
let allClients = [];
let filteredClients = [];
let currentPage = 1;
let pageSize = 10;
let sortField = 'fullName';
let sortAsc = true;

// ── Load ──
document.addEventListener('DOMContentLoaded', function() {
    const urlParams = new URLSearchParams(window.location.search);
    const searchParam = urlParams.get('search');
    if (searchParam) {
        const searchInput = document.getElementById('search-input');
        if (searchInput) searchInput.value = searchParam;
    }
    loadClients();
});

async function loadClients() {
    const tbody = document.getElementById('clients-table-body');
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-400"><i class="fas fa-spinner fa-spin mr-2"></i>Loading clients...</td></tr>';

    try {
        // Get latest snapshot ID first
        const snap = await getJSON('/api/latest-snapshot');
        if (!snap || !snap.id) {
            tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-500">No data available. Go to <a href="/update" class="text-blue-600 underline">Update Monthly Sheet</a> to import.</td></tr>';
            return;
        }
        const clients = await getJSON('/api/snapshot/' + snap.id + '/clients');
        allClients = clients || [];
        filteredClients = [...allClients];
        applySort();
        renderTable();
        updateResultCount();
    } catch (e) {
        console.error('Load clients error:', e);
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-red-500">Error loading clients: ' + e.message + '</td></tr>';
    }
}

// ── Filter ──
function filterClients() {
    const search = (document.getElementById('search-input').value || '').toLowerCase().trim();
    const status = document.getElementById('status-filter').value;
    const deposit = document.getElementById('deposit-filter').value;
    const pnl = document.getElementById('pnl-filter').value;

    filteredClients = allClients.filter(function(c) {
        // Search
        if (search) {
            const name = (c.fullName || '').toLowerCase();
            const account = (c.account || '').toLowerCase();
            const email = (c.email || '').toLowerCase();
            if (name.indexOf(search) === -1 && account.indexOf(search) === -1 && email.indexOf(search) === -1) {
                return false;
            }
        }
        // Status
        if (status && c.status !== status) return false;
        // Deposit
        if (deposit === 'has' && (c.deposit || 0) <= 0) return false;
        if (deposit === 'zero' && (c.deposit || 0) > 0) return false;
        // PnL
        if (pnl === 'profit' && (c.pnl || 0) <= 0) return false;
        if (pnl === 'loss' && (c.pnl || 0) >= 0) return false;
        if (pnl === 'zero' && (c.pnl || 0) !== 0) return false;
        return true;
    });

    currentPage = 1;
    applySort();
    renderTable();
    updateResultCount();
}

// ── Sort ──
function sortClients(field) {
    if (sortField === field) {
        sortAsc = !sortAsc;
    } else {
        sortField = field;
        sortAsc = true;
    }
    applySort();
    renderTable();
}

function applySort() {
    filteredClients.sort(function(a, b) {
        let av = a[sortField] || 0;
        let bv = b[sortField] || 0;
        // Numeric fields
        if (['deposit', 'balance', 'pnl', 'commission', 'commissionTotal', 'equity'].indexOf(sortField) !== -1) {
            av = parseFloat(av) || 0;
            bv = parseFloat(bv) || 0;
        } else {
            av = (av || '').toString().toLowerCase();
            bv = (bv || '').toString().toLowerCase();
        }
        if (av < bv) return sortAsc ? -1 : 1;
        if (av > bv) return sortAsc ? 1 : -1;
        return 0;
    });
}

// ── Pagination ──
function changePage(delta) {
    const totalPages = Math.ceil(filteredClients.length / pageSize) || 1;
    currentPage = Math.max(1, Math.min(totalPages, currentPage + delta));
    renderTable();
}

function changePageSize() {
    pageSize = parseInt(document.getElementById('page-size').value, 10);
    currentPage = 1;
    renderTable();
}

// ── Render ──
function renderTable() {
    const tbody = document.getElementById('clients-table-body');
    if (!tbody) return;

    const start = (currentPage - 1) * pageSize;
    const pageData = filteredClients.slice(start, start + pageSize);
    const totalPages = Math.ceil(filteredClients.length / pageSize) || 1;

    if (pageData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-400">No clients match your filters.</td></tr>';
    } else {
        let html = '';
        pageData.forEach(function(c) {
            const statusColors = {
                'ACTIVE': 'bg-green-100 text-green-800',
                'INACTIVE': 'bg-red-100 text-red-800',
                'NEW': 'bg-purple-100 text-purple-800',
                'NEWLY ACTIVE': 'bg-blue-100 text-blue-800',
                'NEWLY INACTIVE': 'bg-orange-100 text-orange-800',
                'DORMANT': 'bg-gray-100 text-gray-800',
                'DISAPPEARED': 'bg-black text-white'
            };
            const statusClass = statusColors[c.status] || 'bg-gray-100 text-gray-800';
            const pnlClass = (c.pnl || 0) > 0 ? 'text-green-600' : ((c.pnl || 0) < 0 ? 'text-red-600' : 'text-gray-500');
            const pnlPrefix = (c.pnl || 0) > 0 ? '+' : '';

            html += '<tr class="hover:bg-gray-50 transition-colors">';
            html += '<td class="px-4 py-3 border-b"><div class="font-medium text-gray-800">' + (c.fullName || '—') + '</div><div class="text-xs text-gray-400">' + (c.email || '') + '</div></td>';
            html += '<td class="px-4 py-3 border-b font-mono text-gray-600">' + (c.account || '—') + '</td>';
            html += '<td class="px-4 py-3 border-b"><span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium ' + statusClass + '">' + (c.status || '—') + '</span></td>';
            html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(c.deposit).replace('$', '') + '</td>';
            html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(c.balance).replace('$', '') + '</td>';
            html += '<td class="px-4 py-3 border-b text-right ' + pnlClass + ' font-medium">' + pnlPrefix + fmtCurrency(c.pnl).replace('$', '') + '</td>';
            html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(c.commission).replace('$', '') + '</td>';
            html += '<td class="px-4 py-3 border-b"><a href="/client/' + encodeURIComponent(c.account) + '" class="text-blue-600 hover:text-blue-800 text-sm font-medium"><i class="fas fa-user-circle mr-1"></i>View</a></td>';
            html += '</tr>';
        });
        tbody.innerHTML = html;
    }

    // Update pagination
    document.getElementById('page-info').textContent = 'Page ' + currentPage + ' of ' + totalPages;
    document.getElementById('btn-prev').disabled = currentPage <= 1;
    document.getElementById('btn-next').disabled = currentPage >= totalPages;
}

function updateResultCount() {
    const el = document.getElementById('result-count');
    if (el) {
        el.textContent = filteredClients.length + ' of ' + allClients.length + ' clients';
    }
}
