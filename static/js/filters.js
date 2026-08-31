/* WesternFX IB Management — Advanced Filters Page */

async function getJSON(url) {
    const urlWithReferrer = typeof buildUrlWithReferrer === 'function' ? buildUrlWithReferrer(url) : url;
    const r = await fetch(urlWithReferrer);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
}

function fmtCurrency(n) {
    if (n === undefined || n === null) return '$0.00';
    const num = typeof n === 'string' ? parseFloat(n) : n;
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Apply Filters ──
async function applyFilters() {
    const tbody = document.getElementById('filter-results');
    tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-400"><i class="fas fa-spinner fa-spin mr-2"></i>Filtering...</td></tr>';

    const params = new URLSearchParams();
    const status = document.getElementById('f-status').value;
    const depMin = document.getElementById('f-dep-min').value;
    const depMax = document.getElementById('f-dep-max').value;
    const pnlMin = document.getElementById('f-pnl-min').value;
    const pnlMax = document.getElementById('f-pnl-max').value;
    const balMin = document.getElementById('f-bal-min').value;
    const balMax = document.getElementById('f-bal-max').value;
    const commMin = document.getElementById('f-comm-min').value;

    if (status) params.append('status', status);
    if (depMin) params.append('deposit_min', depMin);
    if (depMax) params.append('deposit_max', depMax);
    if (pnlMin) params.append('pnl_min', pnlMin);
    if (pnlMax) params.append('pnl_max', pnlMax);
    if (balMin) params.append('balance_min', balMin);
    if (balMax) params.append('balance_max', balMax);
    if (commMin) params.append('commission_min', commMin);

    try {
        const data = await getJSON('/api/filter-clients?' + params.toString());
        if (!data.success) {
            tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-red-500">' + (data.error || 'Filter failed') + '</td></tr>';
            document.getElementById('filter-count').textContent = '0 results';
            return;
        }
        renderResults(data.clients || []);
        document.getElementById('filter-count').textContent = (data.count || 0) + ' results';
    } catch (e) {
        console.error('Filter error:', e);
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-red-500">Error: ' + e.message + '</td></tr>';
    }
}

function clearFilters() {
    document.getElementById('f-status').value = '';
    document.getElementById('f-dep-min').value = '';
    document.getElementById('f-dep-max').value = '';
    document.getElementById('f-pnl-min').value = '';
    document.getElementById('f-pnl-max').value = '';
    document.getElementById('f-bal-min').value = '';
    document.getElementById('f-bal-max').value = '';
    document.getElementById('f-comm-min').value = '';
    document.getElementById('filter-results').innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-400">Click Apply Filters to see results</td></tr>';
    document.getElementById('filter-count').textContent = '0 results';
}

function renderResults(clients) {
    const tbody = document.getElementById('filter-results');
    if (clients.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-gray-400">No clients match your filters.</td></tr>';
        return;
    }

    const statusColors = {
        'ACTIVE': 'bg-green-100 text-green-800',
        'INACTIVE': 'bg-red-100 text-red-800',
        'NEW': 'bg-purple-100 text-purple-800',
        'NEWLY ACTIVE': 'bg-blue-100 text-blue-800',
        'NEWLY INACTIVE': 'bg-orange-100 text-orange-800',
        'DORMANT': 'bg-gray-100 text-gray-800',
        'DISAPPEARED': 'bg-black text-white'
    };

    let html = '';
    clients.forEach(function(c) {
        const statusClass = statusColors[c.status] || 'bg-gray-100 text-gray-800';
        const pnlClass = (c.pnl || 0) > 0 ? 'text-green-600' : ((c.pnl || 0) < 0 ? 'text-red-600' : 'text-gray-500');
        const pnlPrefix = (c.pnl || 0) > 0 ? '+' : '';
        html += '<tr class="hover:bg-gray-50">';
        html += '<td class="px-4 py-3 border-b"><div class="font-medium text-gray-800">' + (c.fullName || '—') + '</div></td>';
        html += '<td class="px-4 py-3 border-b font-mono text-gray-600">' + (c.account || '—') + '</td>';
        html += '<td class="px-4 py-3 border-b"><span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium ' + statusClass + '">' + (c.status || '—') + '</span></td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(c.deposit).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(c.balance).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right ' + pnlClass + ' font-medium">' + pnlPrefix + fmtCurrency(c.pnl).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(c.commission).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b"><a href="/client/' + encodeURIComponent(c.account) + '" class="text-blue-600 hover:text-blue-800 text-sm font-medium">View</a></td>';
        html += '</tr>';
    });
    tbody.innerHTML = html;
}
