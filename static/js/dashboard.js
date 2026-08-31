/* WesternFX Dashboard v8 — guaranteed valid JS */

function getEl(id) { return document.getElementById(id); }
function setText(id, text) { const el = getEl(id); if (el) el.textContent = text; }

function fmtCurrency(n) {
    if (n === undefined || n === null || isNaN(n)) return '$0.00';
    const num = typeof n === 'string' ? parseFloat(n) : Number(n);
    if (isNaN(num)) return '$0.00';
    return '$' + num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtNumber(n) {
    if (n === undefined || n === null || isNaN(n)) return '0';
    return Number(n).toLocaleString('en-US');
}

let chartInstances = {};

function destroyChart(name) {
    if (chartInstances[name]) { chartInstances[name].destroy(); delete chartInstances[name]; }
}

async function getJSON(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error('HTTP ' + r.status);
    return r.json();
}

async function loadDashboard() {
    try {
        const data = await getJSON('/api/dashboard');
        if (!data.success) {
            const content = getEl('dashboard-content');
            if (content) {
                content.innerHTML = '<div class="bg-white rounded-xl shadow-sm border border-gray-100 p-8 text-center"><i class="fas fa-exclamation-circle text-red-500 text-4xl mb-3"></i><h3 class="text-lg font-semibold text-gray-800">No Data Available</h3><p class="text-gray-500 mt-1">' + (data.error || 'No snapshots found.') + '</p><a href="/update" class="inline-block mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"><i class="fas fa-sync mr-2"></i>Update Monthly</a></div>';
            }
            return;
        }

        populateSnapshotSelector(data.history || []);
        renderKPIs(data.stats);
        renderBlownSection(data.stats);
        renderHighlights(data.stats, data.clients || []);

        if ((data.clients || []).length > 0) {
            renderStatusChart(data.clients);
            renderPnLChart(data.clients);
            renderDepositChart(data.clients);
        }
        renderGrowthChart(data.history || []);
        renderFinancialChart(data.history || []);

        const dateEl = getEl('snapshot-date');
        if (dateEl && data.snapshot && data.snapshot.snapshot_date) {
            dateEl.textContent = new Date(data.snapshot.snapshot_date).toLocaleDateString();
        }
    } catch (e) {
        console.error('Dashboard load error:', e);
        const highlights = getEl('highlights-content');
        if (highlights) highlights.innerHTML = '<p class="text-sm text-red-500">Error: ' + e.message + '</p>';
    }
}

function populateSnapshotSelector(history) {
    const select = getEl('snapshot-select');
    if (!select) return;
    select.innerHTML = '<option value="">Latest Snapshot</option>';
    history.slice().reverse().forEach(function(h) {
        const opt = document.createElement('option');
        opt.value = h.month_label;
        opt.textContent = h.month_label;
        select.appendChild(opt);
    });
    select.addEventListener('change', function() {
        const label = this.value;
        if (!label) { loadDashboard(); return; }
        getJSON('/api/dashboard?month=' + encodeURIComponent(label)).then(function(data) {
            if (data.success) {
                renderKPIs(data.stats);
                renderBlownSection(data.stats);
                renderHighlights(data.stats, data.clients || []);
            }
        });
    });
}

function renderKPIs(stats) {
    const st = stats || {};
    setText('kpi-total', fmtNumber(st.total_clients));
    setText('kpi-active', fmtNumber(st.active));
    setText('kpi-inactive', fmtNumber(st.inactive));
    setText('kpi-profitable', fmtNumber(st.profitable || 0));
    setText('kpi-deposit', fmtCurrency(st.total_deposit));
    setText('kpi-profitable-profit', fmtCurrency(st.profitable_profit || 0));
    setText('kpi-commission', fmtCurrency(st.total_commission));
    setText('kpi-commission-total', fmtCurrency(st.total_commission_total || 0));
    setText('kpi-zero-deposit', fmtNumber(st.zero_deposit || 0));

    const total = st.total_clients || 1;
    setText('kpi-active-pct', Math.round((st.active / total) * 100) + '%');
    setText('kpi-inactive-pct', Math.round((st.inactive / total) * 100) + '%');
    setText('kpi-zero-deposit-pct', Math.round(((st.zero_deposit || 0) / total) * 100) + '%');
}

function renderBlownSection(stats) {
    const section = getEl('blown-section');
    const tbody = getEl('blown-table-body');
    if (!section || !tbody) return;
    const accounts = (stats && stats.blown_accounts) || [];
    if (accounts.length === 0) { section.classList.add('hidden'); return; }
    section.classList.remove('hidden');
    let html = '';
    accounts.forEach(function(c) {
        const loss = (c.deposit || 0) - (c.balance || 0);
        html += '<tr class="border-b border-gray-100"><td class="px-4 py-2 text-sm text-gray-700">' + (c.account || '') + '</td><td class="px-4 py-2 text-sm text-gray-700">' + (c.fullName || '') + '</td><td class="px-4 py-2 text-sm text-gray-700 text-right">' + fmtCurrency(c.deposit) + '</td><td class="px-4 py-2 text-sm text-red-600 text-right font-medium">' + fmtCurrency(c.balance) + '</td><td class="px-4 py-2 text-sm text-red-600 text-right font-medium">' + fmtCurrency(loss) + '</td></tr>';
    });
    html += '<tr class="bg-red-50 font-semibold"><td class="px-4 py-2 text-sm text-gray-800" colspan="2">TOTAL BLOWN: ' + accounts.length + '</td><td class="px-4 py-2 text-sm text-gray-800 text-right" colspan="3"></td></tr>';
    tbody.innerHTML = html;
}

function renderHighlights(stats, clients) {
    const container = getEl('highlights-content');
    if (!container) return;

    let html = '';

    const profitable = (stats && stats.profitable_clients) || [];
    if (profitable.length > 0) {
        html += '<div class="mb-4"><p class="text-xs font-semibold text-emerald-600 uppercase mb-2">🟢 Profitable Clients (' + profitable.length + ')</p>';
        const sorted = profitable.slice().sort(function(a, b) { return (b.profit || 0) - (a.profit || 0); });
        sorted.forEach(function(c) {
            html += '<div class="flex justify-between text-sm py-0.5"><span class="text-gray-700 truncate" style="max-width:55%">' + (c.fullName || c.account || '') + '</span><span class="text-gray-400 text-xs">' + fmtCurrency(c.deposit).replace('$','') + ' → ' + fmtCurrency(c.balance).replace('$','') + '</span><span class="text-emerald-600 font-medium">+' + fmtCurrency(c.profit).replace('$','') + '</span></div>';
        });
        html += '<div class="flex justify-between text-sm py-1 mt-1 border-t border-gray-100"><span class="text-gray-600 font-medium">Total Profit:</span><span class="text-emerald-600 font-bold">+' + fmtCurrency(stats.profitable_profit || 0).replace('$','') + '</span></div></div>';
    } else {
        html += '<div class="mb-4"><p class="text-xs font-semibold text-emerald-600 uppercase mb-2">🟢 Profitable Clients (0)</p><p class="text-sm text-gray-400">No clients with Balance &gt; Deposit.</p></div>';
    }

    const negativeClients = [];
    let totalNegative = 0;
    (clients || []).forEach(function(c) {
        const bal = parseFloat(c.balance);
        if (!isNaN(bal) && bal < 0) {
            negativeClients.push({ account: c.account || '', fullName: c.fullName || '', balance: bal });
            totalNegative += Math.abs(bal);
        }
    });
    if (negativeClients.length > 0) {
        html += '<div class="mb-4"><p class="text-xs font-semibold text-red-600 uppercase mb-2">🔴 Problem: Negative Balance (' + negativeClients.length + ')</p>';
        negativeClients.sort(function(a, b) { return a.balance - b.balance; });
        negativeClients.forEach(function(c) {
            html += '<div class="flex justify-between text-sm py-0.5"><span class="text-gray-700 truncate" style="max-width:60%">' + (c.fullName || c.account || '') + '</span><span class="text-red-600 font-medium">' + fmtCurrency(c.balance) + '</span></div>';
        });
        html += '<div class="flex justify-between text-sm py-1 mt-1 border-t border-gray-100"><span class="text-gray-600 font-medium">Total Negative:</span><span class="text-red-600 font-bold">−' + fmtCurrency(totalNegative).replace('$','') + '</span></div></div>';
    }

    const blown = (stats && stats.blown_accounts) || [];
    if (blown.length > 0) {
        let totalLost = 0;
        blown.forEach(function(c) { totalLost += ((c.deposit || 0) - (c.balance || 0)); });
        html += '<div><p class="text-xs font-semibold text-orange-600 uppercase mb-2">💥 Account Blown (' + blown.length + ')</p><p class="text-sm text-orange-600">Deposit lost: ' + fmtCurrency(totalLost) + '</p></div>';
    }

    container.innerHTML = html;
}

function renderStatusChart(clients) {
    const ctx = getEl('chart-status');
    if (!ctx) return;
    const active = clients.filter(function(c) { return (parseFloat(c.balance) || 0) > 0; }).length;
    const inactive = clients.filter(function(c) { return (parseFloat(c.balance) || 0) <= 0; }).length;
    destroyChart('status');
    chartInstances.status = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: ['Active', 'Inactive'], datasets: [{ data: [active, inactive], backgroundColor: ['#16a34a', '#dc2626'], borderWidth: 2, borderColor: '#fff' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } }
    });
}

function renderGrowthChart(history) {
    const ctx = getEl('chart-growth');
    if (!ctx) return;
    if (!history || history.length === 0) {
        destroyChart('growth');
        chartInstances.growth = new Chart(ctx, { type: 'line', data: { labels: ['No Data'], datasets: [{ data: [0], borderColor: '#e5e7eb', borderDash: [5, 5] }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } } });
        return;
    }

    const labels = history.map(function(h) { return h.month_label; });
    const totalData = history.map(function(h) { return h.total_clients; });
    const activeData = history.map(function(h) { return h.active; });
    const profitableData = history.map(function(h) { return h.profitable || 0; });

    let displayLabels = labels;
    let displayTotal = totalData;
    let displayActive = activeData;
    let displayProfitable = profitableData;

    if (history.length === 1) {
        displayLabels = ['Previous', labels[0]];
        displayTotal = [0, totalData[0]];
        displayActive = [0, activeData[0]];
        displayProfitable = [0, profitableData[0]];
    }

    destroyChart('growth');
    chartInstances.growth = new Chart(ctx, {
        type: 'line',
        data: {
            labels: displayLabels,
            datasets: [
                { label: 'Total', data: displayTotal, borderColor: '#2563eb', backgroundColor: 'rgba(37,99,235,0.1)', tension: 0.3, fill: true, pointRadius: displayTotal.map(function(_, i) { return i === displayTotal.length - 1 ? 6 : 0; }) },
                { label: 'Active', data: displayActive, borderColor: '#16a34a', backgroundColor: 'rgba(22,163,74,0.1)', tension: 0.3, fill: true, pointRadius: displayActive.map(function(_, i) { return i === displayActive.length - 1 ? 6 : 0; }) },
                { label: 'Profitable', data: displayProfitable, borderColor: '#059669', backgroundColor: 'rgba(5,150,105,0.1)', tension: 0.3, fill: true, pointRadius: displayProfitable.map(function(_, i) { return i === displayProfitable.length - 1 ? 6 : 0; }) }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
            scales: { y: { beginAtZero: true }, x: { ticks: { maxRotation: 45, minRotation: 0 } } }
        }
    });
}

function renderFinancialChart(history) {
    const ctx = getEl('chart-financial');
    if (!ctx) return;
    if (!history || history.length === 0) {
        destroyChart('financial');
        chartInstances.financial = new Chart(ctx, { type: 'bar', data: { labels: ['No Data'], datasets: [{ data: [0], backgroundColor: '#e5e7eb' }] }, options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } } });
        return;
    }

    const labels = history.map(function(h) { return h.month_label; });
    destroyChart('financial');
    chartInstances.financial = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                { label: 'Deposit', data: history.map(function(h) { return h.total_deposit; }), backgroundColor: '#2563eb' },
                { label: 'Profitable Profit', data: history.map(function(h) { return h.profitable_profit || 0; }), backgroundColor: '#059669' },
                { label: 'Commission', data: history.map(function(h) { return h.total_commission; }), backgroundColor: '#f59e0b' },
                { label: 'Commission Total', data: history.map(function(h) { return h.total_commission_total || 0; }), backgroundColor: '#d97706' }
            ]
        },
        options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } },
            scales: { y: { beginAtZero: true, ticks: { callback: function(v) { return '$' + v; } } } }
        }
    });
}

function renderPnLChart(clients) {
    const ctx = getEl('chart-pnl');
    if (!ctx) return;
    const profit = clients.filter(function(c) { return (parseFloat(c.pnl) || 0) > 0; }).length;
    const loss = clients.filter(function(c) { return (parseFloat(c.pnl) || 0) < 0; }).length;
    const zero = clients.filter(function(c) { return (parseFloat(c.pnl) || 0) === 0; }).length;
    destroyChart('pnl');
    chartInstances.pnl = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: ['Profit', 'Loss', 'Zero'], datasets: [{ data: [profit, loss, zero], backgroundColor: ['#16a34a', '#dc2626', '#9ca3af'], borderWidth: 2, borderColor: '#fff' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } }
    });
}

function renderDepositChart(clients) {
    const ctx = getEl('chart-deposit');
    if (!ctx) return;
    const noDeposit = clients.filter(function(c) { return (parseFloat(c.deposit) || 0) === 0; }).length;
    const small = clients.filter(function(c) { const d = parseFloat(c.deposit) || 0; return d > 0 && d < 500; }).length;
    const medium = clients.filter(function(c) { const d = parseFloat(c.deposit) || 0; return d >= 500 && d < 2000; }).length;
    const large = clients.filter(function(c) { return (parseFloat(c.deposit) || 0) >= 2000; }).length;
    destroyChart('deposit');
    chartInstances.deposit = new Chart(ctx, {
        type: 'doughnut',
        data: { labels: ['No Deposit', '$1-$499', '$500-$1999', '$2000+'], datasets: [{ data: [noDeposit, small, medium, large], backgroundColor: ['#9ca3af', '#3b82f6', '#8b5cf6', '#10b981'], borderWidth: 2, borderColor: '#fff' }] },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } } } }
    });
}

// Start
document.addEventListener('DOMContentLoaded', loadDashboard);
if (document.readyState !== 'loading') {
    setTimeout(loadDashboard, 0);
}
