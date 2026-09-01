# WesternFX IB Client Management Tool

A Flask-based web application for managing Introducing Broker (IB) client data from WesternFX partnership. Provides monthly snapshot tracking, dashboard analytics, password protection, cloud backup via Dropbox, and HTML upload parsing.

**Version:** 3.0 — Tawhid
**Tech Stack:** Python 3, Flask, SQLite, Tailwind CSS, Chart.js, Dropbox OAuth 2.0

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Configuration Guide](#configuration-guide)
3. [Architecture](#architecture)
4. [Database Schema](#database-schema)
5. [API Endpoints](#api-endpoints)
6. [Key Features](#key-features)
7. [File Structure](#file-structure)
8. [Common Issues & Fixes](#common-issues--fixes)
9. [Dropbox Setup](#dropbox-setup)
10. [Dashboard Rules](#dashboard-rules)
11. [Development Notes](#development-notes)

---

## Quick Start

```bash
cd westernfx-ib-tool
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # or pip install flask dropbox requests
python app.py
```

App runs on `http://0.0.0.0:5000`. For production, set `debug=False` in `app.py`.

---

## Configuration Guide

### Password Protection / Authentication Settings

**File:** `auth.py`

This file handles all password protection and authentication logic:
- **Password hashing:** PBKDF2 with SHA-256 and salt
- **Default password:** `Tawhid+Pradyut` — change this after first login via the Settings page
- **IP whitelisting:** Automatically saves your device's IP after first successful login
- **Session tokens:** Flask session-based auth tokens

**To change the password:**
1. Log in to the app
2. Go to **Settings**
3. Use the "Change Password" form

**Database table:** `auth_ips` stores whitelisted IP addresses.

---

### API 2 Configuration

**File:** `config.py`

```python
DEFAULT_API_URLS = {
    "api2": "YOUR_API2_GOOGLE_APPS_SCRIPT_URL_HERE",
    "api3": "YOUR_API3_GOOGLE_APPS_SCRIPT_URL_HERE",
}
```

**Field in app:** Stored in SQLite `settings` table under key `api2_url`.

**How to update:**
- **Settings page:** Paste your API 2 Google Apps Script URL → Save
- **Direct DB:** Update `settings` table key `api2_url`
- **Environment variable:** Not currently used (all stored in DB)

---

### API 3 Configuration

**File:** `config.py`

Same file as API 2. API 3 is the data source for monthly snapshots.

**Field in app:** Stored in SQLite `settings` table under key `api3_url`.

**How to update:**
- **Settings page:** Paste your API 3 Google Apps Script URL → Save
- **Direct DB:** Update `settings` table key `api3_url`

---

### Dropbox OAuth Configuration

**File:** `dropbox_oauth.py`

Handles the full Dropbox OAuth 2.0 flow with automatic token refresh.

**Credentials file (local dev):** `data/dropbox_oauth_credentials.json`
```json
{
  "app_key": "your_app_key",
  "app_secret": "your_app_secret",
  "redirect_uri": "http://localhost:5000"
}
```

**Environment variables (Railway/production):**
- `DROPBOX_APP_KEY` — Your Dropbox app key
- `DROPBOX_APP_SECRET` — Your Dropbox app secret
- `DROPBOX_REDIRECT_URI` — e.g., `https://your-app.up.railway.app`

**Token storage:** SQLite `settings` table, key `dropbox_oauth_token` (JSON blob with access_token, refresh_token, account_id, expires_in).

---

### Sensitive Token / Key File Paths

| File | Purpose | Sensitivity |
|------|---------|-------------|
| `data/westernfx.db` | SQLite database — contains all client data, snapshots, settings | **HIGH** — backup regularly |
| `data/dropbox_oauth_credentials.json` | Dropbox app credentials (key + secret) | **HIGH** — never commit to public repos |
| `data/dropbox_oauth_token.json` | Dropbox OAuth tokens (legacy, now stored in DB) | **MEDIUM** — may be stale |
| `data/google_oauth_credentials.json` | **REMOVED** in v3.0 | N/A |
| `data/google_drive_credentials.json` | **REMOVED** in v3.0 | N/A |
| `data/google_oauth_token.json` | **REMOVED** in v3.0 | N/A |

**Important:** The `data/` directory is excluded from Git via `.gitignore` to prevent accidental commits of sensitive data.

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

### Auth Endpoints (new in v3.0)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth-check` | POST | Check if current session/IP is authenticated |
| `/api/auth-login` | POST | Submit password, create session, whitelist IP |
| `/api/auth-logout` | POST | Clear session, remove IP whitelist |
| `/api/auth-change-password` | POST | Change the auth password |
| `/api/auth-whitelist` | GET | List all whitelisted IPs |
| `/api/auth-whitelist/<ip>` | DELETE | Remove an IP from whitelist |

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

### `auth_ips` (new in v3.0)
```sql
ip TEXT PRIMARY KEY
authorized_at TEXT
```
Stores whitelisted IP addresses for automatic access.

### `settings`
```sql
key TEXT PRIMARY KEY
value TEXT
```

**Important settings keys:**
- `api2_url`, `api3_url` — Google Apps Script endpoints
- `dropbox_oauth_token` — JSON blob with access_token, refresh_token, account_id (OAuth 2.0)
- `auth_password_hash` — PBKDF2 hash of the login password
- `backup_index` — JSON array of backup metadata
- `last_backup` — ISO datetime of last successful backup

---

## Key Features

### 1. Password Protection (new in v3.0)
- Full-page overlay login screen on every page
- No redirects — pages load normally, overlay covers them
- PBKDF2-hashed password with salt (default: `Tawhid+Pradyut`)
- IP whitelisting: auto-save device IP after first login
- Session token for browser session persistence
- Logout button in sidebar footer
- All API endpoints return 401 for unauthorized requests

### 2. Update Monthly (was "Update Weekly")
Fetches live data from API 3 and saves as a new monthly snapshot. Computes client status by comparing with previous snapshot.

**Status detection rules (computed live, not stored):**
- `balance > 0` → **ACTIVE**
- `balance ≤ 0` → **INACTIVE**
- `balance > deposit` → **PROFITABLE**
- `deposit > 0 AND balance ≤ 0` → **BLOWN** (shown in separate section)

### 3. HTML Upload Parser
Upload a saved WesternFX "My Traders" HTML page. The parser extracts trader rows from Angular `mat-row` elements, deduplicates by `account_number`, and saves as a monthly snapshot.

**Deduplication:** The HTML may render duplicate rows due to virtual scrolling. The parser keeps the first occurrence of each `account_number` and skips subsequent duplicates.

### 4. Dashboard v3.0
- **KPI Cards:** Total, Active, Inactive, Profitable, Total Deposit, Profitable Client Profit, Commission, Commission Total, Zero Deposit count
- **Profitable Clients List:** Names + profit breakdown in Highlights panel
- **Problem: Negative Balance:** Clients with `balance < 0` shown in Highlights
- **Account Blown Table:** Clients with `deposit > 0` and `balance ≤ 0`
- **Charts:** Status Distribution (doughnut), Client Growth (line), Financial Trends (bar), PnL Distribution (doughnut), Deposit Distribution (doughnut)

### 5. Cloud Backup (Dropbox OAuth 2.0)
- **Backup Now:** Uploads `data/westernfx.db` to Dropbox `/westernfx/backups/`
- **Restore:** Downloads a backup and replaces local DB (creates `.backup.YYYYMMDD_HHMMSS` copy first)
- **OAuth 2.0:** Full authorization flow with refresh-token support — "set it and forget it"
- **Token persistence:** Stored in SQLite DB (not ephemeral JSON files) — works on Railway

### 6. Delete Monthly Snapshot
From Update Monthly page, select a snapshot from dropdown and click Delete. Cascades delete all `client_records` and `client_history` linked to that snapshot.

**Known bug:** Returns `{"success": true}` even for non-existent IDs. Check should be added.

---

## File Structure

```
westernfx-ib-tool/
├── app.py                  # Flask routes + API endpoints + auth middleware
├── auth.py                 # Password protection: hashing, IP whitelist, sessions
├── database.py             # All SQLite operations + schema
├── cloud_backup.py         # Dropbox backup/restore with OAuth token refresh
├── dropbox_oauth.py       # Dropbox OAuth 2.0 flow (PKCE, refresh tokens)
├── html_parser.py          # WesternFX HTML → trader data
├── analytics.py            # Dashboard stats computation
├── api_client.py           # Google Apps Script API client
├── config.py               # Constants + default API URLs
├── requirements.txt        # Python dependencies
├── data/
│   └── westernfx.db        # SQLite database (excluded from git)
│   └── dropbox_oauth_credentials.json  # Dropbox app credentials (local dev only)
├── templates/
│   ├── base.html           # Layout with sidebar, nav, auth overlay, logout button
│   ├── dashboard.html      # KPI cards + chart canvases + blown section
│   ├── update.html         # Fetch API 3 + HTML upload + delete snapshot
│   ├── settings.html       # API URLs + Dropbox OAuth + backup controls
│   ├── client_profile.html # Individual client view
│   ├── clients.html        # Client list
│   ├── filters.html        # Advanced filters
│   ├── sync.html           # API 2 sync workflow
│   └── analytics.html      # Custom date range analytics
└── static/js/
    ├── auth.js             # Auth overlay: check, login, logout, shake animation
    ├── dashboard.js        # Chart rendering + KPI population
    ├── update.js           # Fetch/save snapshot + HTML upload + delete
    ├── settings.js         # Save URLs + Dropbox OAuth + backup/restore
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

### Issue: Dropbox token expired (OAuth 2.0)
**Error:** `AuthError('expired_access_token', None)`  
**Fix:** Dropbox OAuth 2.0 is now fully implemented with automatic refresh. If you still see this:
1. Go to **Settings → Cloud Backup**
2. Click **Disconnect**
3. Click **Connect Dropbox** and re-authorize

### Issue: "Dropbox library not installed" on Railway
**Cause:** `dropbox` package was missing from `requirements.txt`. Railway only installs listed packages.  
**Fix:** Added `dropbox==12.0.2` to `requirements.txt`. Redeploy Railway.

### Issue: App process dies during restart
**Cause:** `pkill -f "python.*app"` may match the exec process itself, causing SIGTERM.  
**Fix:** Use `ss -tlnp | grep 5000 | grep -oP 'pid=\K[0-9]+' | xargs kill -9` to kill by port, then `nohup venv/bin/python app.py &`.

---

## Dropbox Setup

1. Go to https://www.dropbox.com/developers/apps
2. Create app: **Scoped access** → **App folder** → Name it "WesternFX Backup"
3. Permissions needed:
   - `files.content.write` — upload backups
   - `files.content.read` — download/restore backups
   - `sharing.read` — list files in shared folders
4. Click **OAuth 2** → Set redirect URI to your app URL (e.g., `https://your-app.up.railway.app`)
5. In the app **Settings → Cloud Backup**, click **Connect Dropbox**
6. Authorize the app in your browser
7. Done! Token auto-refreshes forever.

**Railway env vars:**
```
DROPBOX_APP_KEY=your_app_key_here
DROPBOX_APP_SECRET=your_app_secret_here
DROPBOX_REDIRECT_URI=https://your-app.up.railway.app
```

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

| Variable | Required | Purpose |
|----------|----------|---------|
| `DROPBOX_APP_KEY` | Yes (Railway) | Dropbox app key |
| `DROPBOX_APP_SECRET` | Yes (Railway) | Dropbox app secret |
| `DROPBOX_REDIRECT_URI` | Yes (Railway) | OAuth callback URL |
| `FLASK_SECRET_KEY` | Optional | Flask session secret (auto-generated if not set) |

---

## Changelog

### v3.0 — Tawhid
- **Added password protection** with full-page overlay, IP whitelisting, and session tokens
- **Added Dropbox OAuth 2.0** with automatic token refresh
- **Removed Google Drive** backup (replaced by Dropbox OAuth)
- **Removed unused API 1** — only API 2 and API 3 remain
- Updated watermark to "v3.0 — Tawhid"

### v2.4
- Monthly snapshot tracking
- Dashboard with KPIs and charts
- Cloud backup via Dropbox
- HTML upload parser
- API 2 sync with dry-run preview

---

## License

Private project for WesternFX IB management.
