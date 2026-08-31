/* WesternFX IB Management — Client Profile Page (v2: Monthly)
   Self-contained: includes all helpers inline */

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

let historyChart = null;

// ── Init ──
document.addEventListener('DOMContentLoaded', loadProfile);

async function loadProfile() {
    const account = document.body.dataset.account;
    if (!account) {
        showError('No account specified');
        return;
    }

    try {
        const history = await getJSON('/api/client/' + encodeURIComponent(account) + '/history');
        if (!history || history.length === 0) {
            showError('No history found for this client.');
            return;
        }

        // Use latest record for header
        const latest = history[history.length - 1];
        renderHeader(latest);
        renderCards(latest);
        renderHistoryTable(history);
        renderHistoryChart(history);
    } catch (e) {
        console.error('Profile load error:', e);
        showError('Error loading profile: ' + e.message);
    }
}

function renderHeader(latest) {
    document.getElementById('p-name').textContent = latest.fullName || 'Unknown';
    document.getElementById('p-account').textContent = latest.account || '—';
    document.getElementById('p-email').textContent = latest.email || '—';

    const badge = document.getElementById('p-status-badge');
    if (badge) {
        badge.textContent = latest.status || '—';
        const colors = {
            'ACTIVE': 'bg-green-100 text-green-800',
            'INACTIVE': 'bg-red-100 text-red-800',
            'NEW': 'bg-purple-100 text-purple-800',
            'NEWLY ACTIVE': 'bg-blue-100 text-blue-800',
            'NEWLY INACTIVE': 'bg-orange-100 text-orange-800',
            'DORMANT': 'bg-gray-100 text-gray-800',
            'DISAPPEARED': 'bg-black text-white'
        };
        badge.className = 'inline-block px-2 py-0.5 rounded-full text-xs font-medium ' + (colors[latest.status] || 'bg-gray-100 text-gray-800');
    }

    document.getElementById('p-balance').textContent = fmtCurrency(latest.balance);
    const pnlEl = document.getElementById('p-pnl');
    pnlEl.textContent = fmtCurrency(latest.pnl);
    pnlEl.className = 'text-xl font-bold ' + ((latest.pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600');
}

function renderCards(latest) {
    document.getElementById('p-deposit').textContent = fmtCurrency(latest.deposit);
    document.getElementById('p-equity').textContent = fmtCurrency(latest.equity);
    document.getElementById('p-commission').textContent = fmtCurrency(latest.commission);
    document.getElementById('p-commission-total').textContent = fmtCurrency(latest.commissionTotal);
}

function renderHistoryTable(history) {
    const tbody = document.getElementById('history-table-body');
    if (!tbody) return;

    // Show newest first
    const reversed = history.slice().reverse();
    let html = '';
    reversed.forEach(function(row) {
        const label = row.month_label || row.week_label || '—';
        const pnlClass = (row.pnl || 0) > 0 ? 'text-green-600' : ((row.pnl || 0) < 0 ? 'text-red-600' : 'text-gray-500');
        const pnlPrefix = (row.pnl || 0) > 0 ? '+' : '';
        html += '<tr class="hover:bg-gray-50">';
        html += '<td class="px-4 py-3 border-b"><div class="font-medium text-gray-800">' + label + '</div><div class="text-xs text-gray-400">' + new Date(row.snapshot_date).toLocaleDateString() + '</div></td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(row.deposit).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(row.balance).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(row.equity).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right ' + pnlClass + ' font-medium">' + pnlPrefix + fmtCurrency(row.pnl).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b text-right text-gray-700">' + fmtCurrency(row.commission).replace('$', '') + '</td>';
        html += '<td class="px-4 py-3 border-b"><span class="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">' + (row.status || '—') + '</span></td>';
        html += '</tr>';
    });
    tbody.innerHTML = html;
}

function renderHistoryChart(history) {
    const ctx = document.getElementById('chart-history');
    if (!ctx) return;

    if (historyChart) {
        historyChart.destroy();
        historyChart = null;
    }

    const labels = history.map(function(h) { return h.month_label || h.week_label; });
    const depositData = history.map(function(h) { return h.deposit || 0; });
    const balanceData = history.map(function(h) { return h.balance || 0; });
    const pnlData = history.map(function(h) { return h.pnl || 0; });

    historyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Balance',
                    data: balanceData,
                    borderColor: '#2563eb',
                    backgroundColor: 'rgba(37,99,235,0.1)',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'Deposit',
                    data: depositData,
                    borderColor: '#16a34a',
                    backgroundColor: 'rgba(22,163,74,0.1)',
                    tension: 0.3,
                    fill: true
                },
                {
                    label: 'PnL',
                    data: pnlData,
                    borderColor: '#dc2626',
                    backgroundColor: 'rgba(220,38,38,0.1)',
                    tension: 0.3,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, font: { size: 11 } }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function(v) { return '$' + v; }
                    }
                }
            }
        }
    });
}

function showError(msg) {
    const header = document.getElementById('profile-header');
    if (header) {
        header.innerHTML = '<div class="text-center py-8"><i class="fas fa-exclamation-circle text-red-500 text-3xl mb-2"></i><p class="text-red-600">' + msg + '</p></div>';
    }
}
