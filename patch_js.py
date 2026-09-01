#!/usr/bin/env python3
"""Replace SQLite sync functions in settings.js with new versions."""

import re

JS_FILE = "/home/node/.openclaw/workspace/westernfx-ib-tool/static/js/settings.js"

with open(JS_FILE, "r", encoding="utf-8") as f:
    content = f.read()

# Find and replace the previewSQLiteToApi2 function
OLD_PREVIEW = '''async function previewSQLiteToApi2() {
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
}'''

NEW_PREVIEW = '''async function previewSQLiteToApi2() {
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

        const newClients = result.new_clients || [];
        const changedClients = result.changed_clients || [];
        const unchangedClients = result.unchanged_clients || [];

        // Update summary
        document.getElementById('sqlite-summary-new').textContent = newClients.length;
        document.getElementById('sqlite-summary-update').textContent = changedClients.length;
        document.getElementById('sqlite-summary-unchanged').textContent = unchangedClients.length;

        // New Data section — card layout
        const newSection = document.getElementById('sqlite-preview-new-section');
        const newBody = document.getElementById('sqlite-preview-new-body');
        document.getElementById('sqlite-preview-new-count').textContent = newClients.length;

        if (newClients.length > 0) {
            newSection.classList.remove('hidden');
            let html = '';
            newClients.forEach(function(c) {
                html += '<div class="border border-green-200 rounded-lg p-3 bg-green-50">';
                html += '<div class="flex items-center justify-between mb-1">';
                html += '<span class="font-semibold text-sm">' + (c.fullName || 'Unknown') + '</span>';
                html += '<span class="text-xs font-mono text-gray-500">' + (c.account || '') + '</span>';
                html += '</div>';
                html += '<div class="text-xs text-gray-600 space-y-0.5">';
                html += '<div>Email: ' + (c.email || '—') + '</div>';
                html += '<div>Deposit: ' + (c.deposit !== null && c.deposit !== undefined ? c.deposit : '—') + ' &nbsp;|&nbsp; Balance: ' + (c.balance !== null && c.balance !== undefined ? c.balance : '—') + '</div>';
                html += '</div>';
                html += '</div>';
            });
            newBody.innerHTML = html;
        } else {
            newSection.classList.add('hidden');
            newBody.innerHTML = '';
        }

        // Updating Data section — per-client field change cards
        const changedSection = document.getElementById('sqlite-preview-changed-section');
        const changedBody = document.getElementById('sqlite-preview-changed-body');
        document.getElementById('sqlite-preview-changed-count').textContent = changedClients.length;

        if (changedClients.length > 0) {
            changedSection.classList.remove('hidden');
            let html = '';
            changedClients.forEach(function(c) {
                const changes = c.field_changes || [];
                html += '<div class="border border-amber-200 rounded-lg p-3 bg-amber-50">';
                html += '<div class="flex items-center justify-between mb-2">';
                html += '<span class="font-semibold text-sm">' + (c.fullName || 'Unknown') + '</span>';
                html += '<span class="text-xs font-mono text-gray-500">' + (c.account || '') + '</span>';
                html += '</div>';
                html += '<div class="space-y-1">';
                changes.forEach(function(fc) {
                    const note = fc.note ? ' <span class="text-xs text-gray-400">(' + fc.note + ')</span>' : '';
                    html += '<div class="text-xs flex items-center gap-2">';
                    html += '<span class="font-medium text-amber-700 w-24">' + (fc.field || '') + ':</span>';
                    html += '<span class="text-gray-500 line-through">' + (fc.old !== null && fc.old !== undefined ? fc.old : '—') + '</span>';
                    html += '<i class="fas fa-arrow-right text-gray-400 text-xs"></i>';
                    html += '<span class="text-green-700 font-medium">' + (fc.new !== null && fc.new !== undefined ? fc.new : '—') + '</span>';
                    html += note;
                    html += '</div>';
                });
                html += '</div>';
                html += '</div>';
            });
            changedBody.innerHTML = html;
        } else {
            changedSection.classList.add('hidden');
            changedBody.innerHTML = '';
        }

        // Unchanged Data section — compact tags
        const unchangedSection = document.getElementById('sqlite-preview-unchanged-section');
        const unchangedBody = document.getElementById('sqlite-preview-unchanged-body');
        document.getElementById('sqlite-preview-unchanged-count').textContent = unchangedClients.length;

        if (unchangedClients.length > 0) {
            unchangedSection.classList.remove('hidden');
            let html = '';
            unchangedClients.forEach(function(c) {
                html += '<span class="inline-flex items-center px-2 py-1 rounded-full text-xs bg-gray-100 text-gray-600 border border-gray-200">';
                html += '<span class="font-medium">' + (c.fullName || 'Unknown') + '</span>';
                html += '<span class="font-mono text-gray-400 ml-1">' + (c.account || '') + '</span>';
                html += '</span>';
            });
            unchangedBody.innerHTML = html;
        } else {
            unchangedSection.classList.add('hidden');
            unchangedBody.innerHTML = '';
        }

        // Show/hide Sync Now button
        const applySection = document.getElementById('sqlite-apply-section');
        if (newClients.length > 0 || changedClients.length > 0) {
            applySection.classList.remove('hidden');
            status.innerHTML = '<span class="text-green-600"><i class="fas fa-check-circle mr-1"></i> ' + newClients.length + ' new, ' + changedClients.length + ' to update, ' + unchangedClients.length + ' unchanged</span>';
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
}'''

if OLD_PREVIEW not in content:
    print("ERROR: Could not find old previewSQLiteToApi2")
    exit(1)

content = content.replace(OLD_PREVIEW, NEW_PREVIEW)
print("✓ Replaced previewSQLiteToApi2")

# Replace applySQLiteToApi2 — only change the button text from "Apply Changes to API 2" to "Sync Now"
content = content.replace(
    "btn.innerHTML = '<i class=\"fas fa-cloud-upload-alt mr-1\"></i>Apply Changes to API 2';",
    "btn.innerHTML = '<i class=\"fas fa-cloud-upload-alt mr-1\"></i>Sync Now';"
)
content = content.replace(
    "btn.innerHTML = '<i class=\"fas fa-spinner fa-spin mr-1\"></i>Applying...';",
    "btn.innerHTML = '<i class=\"fas fa-spinner fa-spin mr-1\"></i>Syncing...';"
)
print("✓ Updated applySQLiteToApi2 button labels")

# Replace pollSQLiteSyncProgress button text
content = content.replace(
    "btn.innerHTML = '<i class=\"fas fa-cloud-upload-alt mr-1\"></i>Apply Changes to API 2';",
    "btn.innerHTML = '<i class=\"fas fa-cloud-upload-alt mr-1\"></i>Sync Now';"
)
print("✓ Updated pollSQLiteSyncProgress button labels")

with open(JS_FILE, "w", encoding="utf-8") as f:
    f.write(content)

print("settings.js updated successfully.")
