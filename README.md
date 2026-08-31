# WesternFX IB Client Management Tool

A Flask-based web application for managing Introducing Broker (IB) client data from WesternFX partnership. Provides monthly snapshot tracking, dashboard analytics, cloud backup via Dropbox, and HTML upload parsing.

**Version:** 2.4  
**Tech Stack:** Python 3, Flask, SQLite, Tailwind CSS, Chart.js, Dropbox API

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Database Schema](#database-schema)
4. [API Endpoints](#api-endpoints)
5. [Key Features](#key-features)
6. [File Structure](#file-structure)
7. [Common Issues & Fixes](#common-issues--fixes)
8. [Dropbox Setup](#dropbox-setup)
9. [Dashboard Rules](#dashboard-rules)
10. [Development Notes](#development-notes)

---

## Quick Start

```bash
cd westernfx-ib-tool
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # or pip install flask dropbox requests
python app.py
```

App runs on `http://0.0.0.0:5000`. For production, set `debug=False` in `app.py` (line ~793).

---

## Architecture

### Backend (`app.py`)
Flask app with these route categories:

| Route | Purpose |
|-------|---------|
| `/` | Dashboard |
| `/clients` | Client list with filters |
| `/client/<account>` | Individual client profile |
| `/update` | Monthly snapshot workflow + HTML upload |
| `/sync` | Sync API 2 with API 3 |
| `/filters` | Advanced client filters |
| `/analytics` | Custom date range analytics |
| `/settings` | API URLs + Dropbox token + backup controls |

### API Endpoints (`/api/*`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/dashboard` | GET | KPIs, stats, clients, history for charts |
| `/api/fetch-api3` | POST | Fetch live data from API 3 (preview) |
| `/api/save-snapshot` | POST | Save API 3 data as new monthly snapshot |
| `/api/snapshot/<id>` | DELETE | Delete a monthly snapshot + cascade records |
| `/api/clients` | GET | Filterable client list |
| `/api/client/<account>` | GET | Single client details + history |
| `/api/referrers` | GET | List of unique referrers |
| `/api/sync-api2` | POST | Detect new/changed clients for API 2 sync |
| `/api/sync-api2/<task_id>` | GET | Sync progress polling |
| `/api/settings` | GET/POST | Read/write settings |
| `/api/test-api` | POST | Test API connectivity |
| `/api/snapshots` | GET | All monthly snapshots |
| `/api/latest-snapshot` | GET | Most recent snapshot |
| `/api/history/<account>` | GET | Change history for a client |
| `/api/backup-now` | POST | Trigger Dropbox backup |
| `/api/backups` | GET | List backups from Dropbox (live query) |
| `/api/restore` | POST | Restore DB from Dropbox backup |
| `/api/backup-status` | GET | Last backup time + connection status |
| `/api/export-clients` | GET | Export CSV of current snapshot |
| `/api/parse-html` | POST | Parse WesternFX HTML → trader data preview |
| `/api/save-html-snapshot` | POST | Save parsed HTML data as monthly snapshot |

### Database (`database.py`)
SQLite file: `data/westernfx.db`

---

## Database Schema

### `monthly_snapshots`
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
month_label TEXT       -- e.g., "2026-08"
snapshot_date TEXT     -- ISO datetime
raw_json TEXT          -- Original API response JSON
```

**Migration note:** Old table `weekly_snapshots` still exists as a safety copy. All new code uses `monthly_snapshots`.

### `client_records`
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
snapshot_id INTEGER    -- FK to monthly_snapshots
account TEXT
fullName TEXT
email TEXT
status TEXT            -- ACTIVE / INACTIVE / NEW / PROFITABLE
deposit REAL
balance REAL
equity REAL
pnl REAL
commission REAL
commissionTotal REAL
referred_by TEXT       -- From API 2 "Referred by" field
```

### `client_history`
```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
snapshot_id INTEGER
account TEXT
field_name TEXT
old_value TEXT
new_value TEXT
change_date TEXT
```

### `settings`
```sql
key TEXT PRIMARY KEY
value TEXT
```

**Important settings keys:**
- `api1_url`, `api2_url`, `api3_url` — Google Apps Script endpoints
- `dropbox_token` — OAuth access token (short-lived, ~4 hours)
- `backup_index` — JSON array of backup metadata
- `last_backup` — ISO datetime of last successful backup

---

## Key Features

### 1. Update Monthly (was "Update Weekly")
Fetches live data from API 3 and saves as a new monthly snapshot. Computes client status by comparing with previous snapshot.

**Status detection rules (computed live, not stored):**
- `balance > 0` → **ACTIVE**
- `balance ≤ 0` → **INACTIVE**
- `balance > deposit` → **PROFITABLE**
- `deposit > 0 AND balance ≤ 0` → **BLOWN** (shown in separate section)

### 2. HTML Upload Parser
Upload a saved WesternFX "My Traders" HTML page. The parser extracts trader rows from Angular `mat-row` elements, deduplicates by `account_number`, and saves as a monthly snapshot.

**Deduplication:** The HTML may render duplicate rows due to virtual scrolling. The parser keeps the first occurrence of each `account_number` and skips subsequent duplicates.

### 3. Dashboard v2.4
- **KPI Cards:** Total, Active, Inactive, Profitable, Total Deposit, Profitable Client Profit, Commission, Commission Total, Zero Deposit count
- **Profitable Clients List:** Names + profit breakdown in Highlights panel
- **Problem: Negative Balance:** Clients with `balance < 0` shown in Highlights
- **Account Blown Table:** Clients with `deposit > 0` and `balance ≤ 0`
- **Charts:** Status Distribution (doughnut), Client Growth (line), Financial Trends (bar), PnL Distribution (doughnut), Deposit Distribution (doughnut)

### 4. Cloud Backup (Dropbox)
- **Backup Now:** Uploads `data/westernfx.db` to Dropbox `/westernfx/backups/`
- **Restore:** Downloads a backup and replaces local DB (creates `.backup.YYYYMMDD_HHMMSS` copy first)
- **Live Sync:** `/api/backups` queries Dropbox directly (not cached) so deleted files disappear immediately

### 5. Delete Monthly Snapshot
From Update Monthly page, select a snapshot from dropdown and click Delete. Cascades delete all `client_records` and `client_history` linked to that snapshot.

**Known bug:** Returns `{"success": true}` even for non-existent IDs. Check should be added.

---

## File Structure

```
westernfx-ib-tool/
├── app.py                  # Flask routes + API endpoints
├── database.py             # All SQLite operations
├── cloud_backup.py         # Dropbox upload/download/list
├── html_parser.py          # WesternFX HTML → trader data
├── analytics.py            # Dashboard stats computation
├── api_client.py           # Google Apps Script API client
├── config.py               # Constants + default URLs
├── requirements.txt        # Python dependencies
├── data/
│   └── westernfx.db        # SQLite database
├── templates/
│   ├── base.html           # Layout with sidebar, nav, cache meta tags
│   ├── dashboard.html      # KPI cards + chart canvases + blown section
│   ├── update.html         # Fetch API 3 + HTML upload + delete snapshot
│   ├── settings.html       # API URLs + Dropbox token + backup controls
│   ├── client_profile.html # Individual client view
│   ├── clients.html        # Client list
│   ├── filters.html        # Advanced filters
│   ├── sync.html           # API 2 sync workflow
│   └── analytics.html      # Custom date range analytics
└── static/js/
    ├── dashboard.js        # Chart rendering + KPI population (v8)
    ├── update.js           # Fetch/save snapshot + HTML upload + delete
    ├── settings.js         # Save URLs/token + backup/restore (v3)
    ├── client_profile.js   # Client detail view
    ├── clients.js          # Client list + filters
    ├── sync.js             # API 2 sync detection
    └── main.js             # Shared helpers (getJSON, postJSON, showToast)
```

---

## Common Issues & Fixes

### Issue: Dashboard blank / charts not rendering / "Loading..." stuck
**Root causes seen:**
1. **JS syntax error** in `dashboard.js` — prevents entire script from loading. Check with `node -c dashboard.js`.
2. **Browser caching old HTML** — even with `<meta no-cache>` tags, previously cached HTML may not contain new DOM elements. **Fix:** Bump JS version in template (e.g., `?v=8` → `?v=12`) AND tell user to `Ctrl+Shift+R`.
3. **`DOMContentLoaded` fired before script loaded** — script is at bottom of page. Added fallback: `if (document.readyState !== 'loading') setTimeout(loadDashboard, 0);`
4. **Flask `debug=True`** — reloader kills background processes. **Must be `debug=False`** for stable `nohup` deployment.

### Issue: Backup list shows "undefined" / wrong field names
**Cause:** `settings.js` read `b.filename` and `b.date` but backend sent `b.name` and `b.created_at`.  
**Fix:** Updated `settings.js` to use correct field names + compute `sizeMB = b.size / (1024*1024)`.

### Issue: Deleted Dropbox files still show in backup list
**Cause:** `list_backups()` used a local cached index stored in SQLite `settings` table.  
**Fix:** Rewrote `list_backups()` to query Dropbox `files_list_folder('/westernfx/backups')` live every time.

### Issue: Dropbox token expired
**Error:** `AuthError('expired_access_token', None)`  
**Fix:** Dropbox short-lived tokens expire in ~4 hours. Go to Dropbox App Console → Generate new access token → paste in Settings page → Save Token.

### Issue: App process dies during restart
**Cause:** `pkill -f "python.*app"` may match the exec process itself, causing SIGTERM.  
**Fix:** Use `ss -tlnp | grep 5000 | grep -oP 'pid=\K[0-9]+' | xargs kill -9` to kill by port, then `nohup venv/bin/python app.py &`.

### Issue: `cloud_backup.py` missing `files.metadata.read` scope
**Error:** `unexpected use of the catch-all tag 'other'`  
**Workaround:** Instead of querying Dropbox metadata API, query `files_list_folder` which works with `files.content.write` + `files.content.read` scopes.

---

## Dropbox Setup

1. Go to https://www.dropbox.com/developers/apps
2. Create app: **Scoped access** → **App folder** → Name it "WesternFX Backup"
3. Permissions needed:
   - `files.content.write` — upload backups
   - `files.content.read` — download/restore backups
4. Click **Generate** next to "Access token"
5. Copy token → paste in app Settings → Save Token
6. Click **Backup Now** to test

**Note:** The token expires in ~4 hours. For long-term use, implement OAuth refresh flow (not currently implemented — tokens are manual).

---

## Dashboard Rules

### Status Computation (always from raw data, never from stored `status` column)

| Condition | Label | Color |
|-----------|-------|-------|
| `balance > 0` | Active | Green |
| `balance ≤ 0` | Inactive | Red |
| `balance > deposit` | Profitable | Emerald |
| `deposit > 0 AND balance ≤ 0` | Blown | Red/Orange |
| `balance < 0` | Problem (Negative Balance) | Red |

### KPIs
- **Profitable Client Profit** = `Σ(balance - deposit)` for all clients where `balance > deposit`
- **Total Deposit** = `Σ(deposit)` for all clients
- **Commission** = `Σ(commission)`
- **Commission Total** = `Σ(commissionTotal)`
- **Zero Deposit** = count where `deposit == 0`

---

## Development Notes

### Cache Busting
JS files are loaded with version queries: `dashboard.js?v=12`, `settings.js?v=3`. Bump these when making JS changes to force browser reload.

### `app.py` debug mode
**CRITICAL:** Production must use `app.run(host="0.0.0.0", port=5000, debug=False)`. With `debug=True`, Flask's reloader will kill any background processes including `nohup`.

### Database Migration (legacy → monthly)
If migrating from old `weekly_snapshots`:
1. Create `monthly_snapshots` table with same schema
2. Copy data: `INSERT INTO monthly_snapshots SELECT * FROM weekly_snapshots`
3. Update all code references from `week_label` → `month_label`
4. Keep `weekly_snapshots` as safety copy until verified

### API Data Format (API 3)
Expected JSON array of objects with fields:
```json
{
  "account": "2121255359",
  "fullName": "John Doe",
  "email": "john@example.com",
  "deposit": 1000.00,
  "balance": 950.00,
  "equity": 960.00,
  "pnl": -50.00,
  "commission": 5.00,
  "commissionTotal": 10.00
}
```

### HTML Parser Input
Saved WesternFX "My Traders" page. The parser looks for:
- `mat-row` elements (Angular Material table rows)
- Columns in order: Full Name | Email | Account | Equity | Balance | PnL | Deposit | Commission | Commission Total
- Extracts text content and maps to structured objects
- Deduplicates by `account_number` (keeps first occurrence)

---

## Environment Variables

None required. All config is in the SQLite `settings` table or `config.py` defaults.

---

## License

Private project for WesternFX IB management.
