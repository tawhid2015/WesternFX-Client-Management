"""
WesternFX IB Management Tool — Flask Application (v2: Monthly + Cloud Backup + Auth)
=================================================================================
Main application entry point.
"""
import csv
import io
import json
import os
import shutil
from datetime import datetime

from flask import Flask, render_template, jsonify, request, Response, session, make_response

from config import (
    DATABASE_PATH,
    DEFAULT_API_URLS,
    API3_HEADERS,
    REFERRER_OPTIONS,
)
from database import init_db, get_setting, set_setting, get_all_settings
from database import (
    create_snapshot,
    get_latest_snapshot,
    get_all_snapshots,
    save_client_records,
    get_clients_by_snapshot,
    get_client_monthly_history,
    delete_snapshot,
)
from html_parser import parse_westernfx_html, get_summary
from api_client import test_api, api3_read, api12_read, api12_add, api12_update
from cloud_backup import backup, restore, list_backups, get_status
import threading
import time
import uuid

# Password protection
from auth import (
    check_password,
    authenticate_request,
    generate_session_token,
    SESSION_KEY,
    get_client_ip,
    is_ip_whitelisted,
    whitelist_ip,
    remove_whitelisted_ip,
    get_all_whitelisted_ips,
    change_password,
    DEFAULT_PASSWORD,
)

# Dropbox OAuth imports
try:
    from dropbox_oauth import get_auth_url, exchange_code, test_connection, disconnect as disconnect_dropbox
except ImportError:
    get_auth_url = exchange_code = test_connection = disconnect_dropbox = None

# ── Global sync task tracker ───────────────────────────────
# {task_id: {"status": "running|done|error", "total": N, "done": N, "results": [...], "error": str}}
sync_tasks = {}


def _balance_to_active_inactive(balance):
    """Convert balance to Active/Inactive status.
    balance <= 0 → Inactive
    balance > 0 → Active
    """
    try:
        b = float(balance) if balance is not None else 0
    except (ValueError, TypeError):
        b = 0
    return "Inactive" if b <= 0 else "Active"


def _run_sync_task(task_id, referrer, api2_url, new_clients, changed_clients):
    """Background thread: sync clients one by one."""
    try:
        results = []
        all_ops = []
        
        # Build operation list: (type, client_data)
        for c in new_clients:
            all_ops.append(("add", c))
        for c in changed_clients:
            all_ops.append(("update", c))
        
        total = len(all_ops)
        sync_tasks[task_id] = {"status": "running", "total": total, "done": 0, "results": [], "error": None}
        
        # Detect available columns from first API 2 record
        api2_sample = api12_read(api2_url)
        available_cols = set()
        if isinstance(api2_sample, list) and api2_sample:
            available_cols = set(api2_sample[0].keys())
        
        for i, (op_type, client) in enumerate(all_ops):
            try:
                if op_type == "add":
                    # Build student data for new client
                    active_inactive = _balance_to_active_inactive(client.get("balance"))
                    student_data = {
                        "AccountId": client["account"],
                        "StudentName": client.get("fullName", ""),
                        "MailId": client.get("email", ""),
                        "Deposit": client.get("deposit"),
                        "CurrentBalance": client.get("balance"),
                        "ReferredBy": referrer,
                        "ActiveInactive": active_inactive,
                    }
                    # Remove None/empty values
                    student_data = {k: v for k, v in student_data.items() if v is not None and v != ""}
                    result = api12_add(api2_url, student_data)
                else:  # update
                    # Column name → API parameter name (no spaces)
                    PARAM_MAP = {
                        "Student Name": "StudentName",
                        "Mail Id": "MailId",
                        "Deposit": "Deposit",
                        "Current Balance": "CurrentBalance",
                        "Active/Inactive": "ActiveInactive",
                    }
                    changed_fields = {}
                    for fc in client.get("field_changes", []):
                        api2_field = fc.get("api2_field")
                        # Rule: never overwrite an existing email in API 2
                        if api2_field == "Mail Id":
                            continue
                        if api2_field in available_cols or api2_field in PARAM_MAP:
                            param_name = PARAM_MAP.get(api2_field, api2_field)
                            changed_fields[param_name] = fc["new"]
                    
                    if changed_fields:
                        print(f"[SYNC UPDATE] account={client['account']} fields={changed_fields}")
                        result = api12_update(api2_url, {"AccountId": client["account"]}, changed_fields)
                        print(f"[SYNC UPDATE] account={client['account']} result={result}")
                    else:
                        result = {"success": True, "skipped": True, "reason": "No valid columns to update"}
                
                success = True
                error = None
                if isinstance(result, dict):
                    success = result.get("success", True)
                    error = result.get("error")
                
                results.append({
                    "account": client["account"],
                    "type": op_type,
                    "success": success,
                    "error": error,
                })
            except Exception as e:
                results.append({
                    "account": client.get("account", "unknown"),
                    "type": op_type,
                    "success": False,
                    "error": str(e),
                })
            
            sync_tasks[task_id]["done"] = i + 1
            sync_tasks[task_id]["results"] = results
            time.sleep(0.5)  # Small delay between operations
        
        sync_tasks[task_id]["status"] = "done"
    except Exception as e:
        sync_tasks[task_id] = {"status": "error", "total": 0, "done": 0, "results": [], "error": str(e)}


def _run_sqlite_to_api2_sync_task(task_id, api2_url, sqlite_clients, api2_by_account):
    """Background thread: push SQLite snapshot clients to API 2 one by one."""
    try:
        results = []
        all_ops = []
        
        # Build operation list
        for c in sqlite_clients:
            account = str(c.get("account", "")).strip()
            if not account:
                continue
            if account not in api2_by_account:
                all_ops.append(("add", c))
            else:
                all_ops.append(("update", c))
        
        total = len(all_ops)
        sync_tasks[task_id] = {"status": "running", "total": total, "done": 0, "results": [], "error": None}
        
        for i, (op_type, client) in enumerate(all_ops):
            try:
                account = str(client.get("account", "")).strip()
                if op_type == "add":
                    active_inactive = _balance_to_active_inactive(client.get("balance"))
                    student_data = {
                        "AccountId": account,
                        "StudentName": client.get("fullName", ""),
                        "MailId": client.get("email", ""),
                        "Deposit": client.get("deposit"),
                        "CurrentBalance": client.get("balance"),
                        "ReferredBy": client.get("referred_by", ""),
                        "ActiveInactive": active_inactive,
                    }
                    # Remove None/empty values
                    student_data = {k: v for k, v in student_data.items() if v is not None and v != ""}
                    result = api12_add(api2_url, student_data)
                else:  # update
                    api2_rec = api2_by_account.get(account, {})
                    changed_fields = {}
                    
                    # Deposit
                    old_deposit = api2_rec.get("Deposit")
                    new_deposit = client.get("deposit")
                    try:
                        o = float(old_deposit) if old_deposit is not None else None
                        n = float(new_deposit) if new_deposit is not None else None
                        if o is None or n is None or abs(o - n) > 0.001:
                            changed_fields["Deposit"] = new_deposit
                    except (ValueError, TypeError):
                        if str(old_deposit) != str(new_deposit):
                            changed_fields["Deposit"] = new_deposit
                    
                    # Current Balance
                    old_balance = api2_rec.get("Current Balance")
                    new_balance = client.get("balance")
                    try:
                        o = float(old_balance) if old_balance is not None else None
                        n = float(new_balance) if new_balance is not None else None
                        if o is None or n is None or abs(o - n) > 0.001:
                            changed_fields["CurrentBalance"] = new_balance
                    except (ValueError, TypeError):
                        if str(old_balance) != str(new_balance):
                            changed_fields["CurrentBalance"] = new_balance
                    
                    # Active/Inactive derived from balance
                    old_status = str(api2_rec.get("Active/Inactive", "")).strip().lower()
                    new_status = _balance_to_active_inactive(client.get("balance"))
                    if old_status not in ("active", "inactive"):
                        old_status = "active" if old_status.startswith("act") else "inactive"
                    if old_status != new_status.lower():
                        changed_fields["ActiveInactive"] = new_status
                    
                    # Never overwrite MailId if it already exists in API 2
                    old_email = api2_rec.get("Mail Id")
                    if old_email:
                        changed_fields.pop("MailId", None)
                    
                    if changed_fields:
                        print(f"[SQLITE→API2 UPDATE] account={account} fields={changed_fields}")
                        result = api12_update(api2_url, {"AccountId": account}, changed_fields)
                        print(f"[SQLITE→API2 UPDATE] account={account} result={result}")
                    else:
                        result = {"success": True, "skipped": True, "reason": "No valid columns to update"}
                
                success = True
                error = None
                if isinstance(result, dict):
                    success = result.get("success", True)
                    error = result.get("error")
                
                results.append({
                    "account": account,
                    "type": op_type,
                    "success": success,
                    "error": error,
                })
            except Exception as e:
                results.append({
                    "account": client.get("account", "unknown"),
                    "type": op_type,
                    "success": False,
                    "error": str(e),
                })
            
            sync_tasks[task_id]["done"] = i + 1
            sync_tasks[task_id]["results"] = results
            time.sleep(0.5)  # Small delay between operations
        
        sync_tasks[task_id]["status"] = "done"
    except Exception as e:
        sync_tasks[task_id] = {"status": "error", "total": 0, "done": 0, "results": [], "error": str(e)}

from analytics import detect_status, compute_snapshot_stats, compare_snapshots

app = Flask(__name__)

# Use a stable secret key derived from env var, fallback to random
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
if isinstance(app.secret_key, str):
    app.secret_key = app.secret_key.encode()

# ── Authentication ────────────────────────────────────────
# Routes that are EXEMPT from auth checks
_AUTH_EXEMPT_ROUTES = {
    "api_auth_check",
    "api_auth_login",
    "api_auth_logout",
    "static",
}

def _requires_auth():
    """Check if the current endpoint requires authentication."""
    # Static files are always exempt
    if request.endpoint == "static":
        return False
    return request.endpoint not in _AUTH_EXEMPT_ROUTES

@app.before_request
def auth_before_request():
    """Intercept all requests and require auth except exempt routes."""
    if not _requires_auth():
        return None  # No auth needed
    is_authed, client_ip = authenticate_request(request, session)
    if not is_authed:
        # For API routes, return JSON unauthorized
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "Unauthorized", "needs_auth": True}), 401
        # For page routes, allow HTML to load — the auth overlay blocks access
        return None
    return None


# ── Disable caching for development ───────────────────────
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ── Initialize database on startup ────────────────────────
init_db()


# ── Helpers ───────────────────────────────────────────────

def _get_referrer_from_request():
    """Read referrer filter from request query param."""
    referrer = request.args.get("referrer", "")
    if referrer:
        referrer = referrer.strip()
    return referrer or None


def _get_latest_snapshot_with_clients(referrer=None):
    """Get the latest snapshot with client records loaded, optionally filtered by referrer."""
    snap = get_latest_snapshot()
    if not snap:
        return None, []
    clients = get_clients_by_snapshot(snap["id"], referrer=referrer)
    return snap, clients


def _get_snapshot_with_clients(snapshot_id, referrer=None):
    """Get a specific snapshot with client records, optionally filtered by referrer."""
    from database import get_snapshot_by_id
    snap = get_snapshot_by_id(snapshot_id)
    if not snap:
        return None, []
    clients = get_clients_by_snapshot(snapshot_id, referrer=referrer)
    return snap, clients


# ── Context Processor ───────────────────────────────────
@app.context_processor
def inject_globals():
    return {
        "app_name": "WesternFX IB Management",
        "current_year": datetime.utcnow().year,
    }


# ── Auth Routes (EXEMPT from auth check) ──────────────────

@app.route("/api/auth-check", methods=["GET", "POST"])
def api_auth_check():
    """Check if current session/IP is authenticated."""
    is_authed, client_ip = authenticate_request(request, session)
    return jsonify({
        "success": True,
        "authenticated": is_authed,
        "ip": client_ip,
    })


@app.route("/api/auth-login", methods=["POST"])
def api_auth_login():
    """Submit password for authentication."""
    data = request.get_json() or {}
    password = data.get("password", "")
    
    if not password:
        return jsonify({"success": False, "error": "Password required"}), 400
    
    if check_password(password):
        # Create session token
        session[SESSION_KEY] = generate_session_token()
        # Whitelist the IP
        client_ip = get_client_ip(request)
        whitelist_ip(client_ip)
        return jsonify({"success": True, "message": "Authenticated", "ip": client_ip})
    else:
        return jsonify({"success": False, "error": "Incorrect password"}), 401


@app.route("/api/auth-logout", methods=["POST"])
def api_auth_logout():
    """Logout — clear session and remove IP whitelist."""
    client_ip = get_client_ip(request)
    remove_whitelisted_ip(client_ip)
    session.pop(SESSION_KEY, None)
    return jsonify({"success": True, "message": "Logged out"})


@app.route("/api/auth-change-password", methods=["POST"])
def api_auth_change_password():
    """Change the authentication password."""
    data = request.get_json() or {}
    current = data.get("current_password", "")
    new_pass = data.get("new_password", "")
    
    if not current or not new_pass:
        return jsonify({"success": False, "error": "Both current and new password required"}), 400
    
    if not check_password(current):
        return jsonify({"success": False, "error": "Current password is incorrect"}), 401
    
    if len(new_pass) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400
    
    change_password(new_pass)
    return jsonify({"success": True, "message": "Password changed successfully"})


@app.route("/api/auth-whitelist", methods=["GET"])
def api_auth_whitelist():
    """Get all whitelisted IPs."""
    ips = get_all_whitelisted_ips()
    return jsonify({"success": True, "ips": ips})


@app.route("/api/auth-whitelist/<ip>", methods=["DELETE"])
def api_auth_remove_ip(ip):
    """Remove an IP from the whitelist."""
    remove_whitelisted_ip(ip)
    return jsonify({"success": True, "message": f"Removed {ip}"})


# ── Routes ────────────────────────────────────────────────

@app.route("/")
def dashboard():
    """Main dashboard with KPIs and charts."""
    return render_template("dashboard.html")


@app.route("/clients")
def clients():
    """All clients table with filters."""
    return render_template("clients.html")


@app.route("/client/<account>")
def client_profile(account):
    """Individual client profile page."""
    return render_template("client_profile.html", account=account)


@app.route("/filters")
def filters():
    """Advanced filters page."""
    return render_template("filters.html")


@app.route("/update")
def update_monthly():
    """Monthly sheet update workflow."""
    return render_template("update.html")


@app.route("/analytics")
def analytics():
    """Advanced analytics with custom date ranges."""
    return render_template("analytics.html")


@app.route("/settings")
def settings():
    """Settings page — edit API URLs and cloud backup."""
    return render_template("settings.html")


@app.route("/sync")
def sync():
    """Sync API 2 with API 3 data."""
    return render_template("sync.html")


# ── API Endpoints ─────────────────────────────────────────

@app.route("/api/dashboard", methods=["GET"])
def api_dashboard():
    """Return dashboard KPIs and chart data for the latest snapshot."""
    referrer = _get_referrer_from_request()
    snap, clients = _get_latest_snapshot_with_clients(referrer=referrer)
    if not snap:
        return jsonify({"success": False, "error": "No snapshots found"})
    stats = compute_snapshot_stats(clients)

    # Historical data for charts — fetch all snapshots' stats
    all_snaps = get_all_snapshots()
    history = []
    for s in all_snaps:
        sc = get_clients_by_snapshot(s["id"])
        st = compute_snapshot_stats(sc)
        history.append({
            "month_label": s.get("month_label", s.get("week_label", "")),
            "snapshot_date": s["snapshot_date"],
            "total_clients": st["total_clients"],
            "active": st["active"],
            "inactive": st["inactive"],
            "profitable": st["profitable"],
            "blown": st["blown"],
            "profitable_profit": st["profitable_profit"],
            "zero_deposit": st["zero_deposit"],
            "total_deposit": st["total_deposit"],
            "total_commission": st["total_commission"],
            "total_commission_total": st["total_commission_total"],
            "total_balance": st["total_balance"],
            "total_equity": st["total_equity"],
        })

    return jsonify({
        "success": True,
        "snapshot": snap,
        "stats": stats,
        "clients": clients,
        "history": history,
        "referrer_filter": referrer,
    })


@app.route("/api/settings", methods=["GET"])
def api_get_settings():
    """Return all current settings."""
    return jsonify(get_all_settings())


@app.route("/api/settings", methods=["POST"])
def api_save_settings():
    """Save one or more settings."""
    data = request.get_json() or {}
    for key, value in data.items():
        set_setting(key, str(value))
    return jsonify({"success": True})


@app.route("/api/test-api", methods=["POST"])
def api_test_api():
    """Test connectivity to an API."""
    data = request.get_json() or {}
    api_key = data.get("api")  # "api1", "api2", or "api3"
    url = data.get("url") or get_setting(api_key + "_url", "")
    if not url:
        return jsonify({"success": False, "error": "No URL provided"})
    result = test_api(url)
    return jsonify(result)


@app.route("/api/snapshots", methods=["GET"])
def api_get_snapshots():
    """Return all monthly snapshots."""
    return jsonify(get_all_snapshots())


@app.route("/api/latest-snapshot", methods=["GET"])
def api_latest_snapshot():
    """Return the most recent snapshot."""
    snap = get_latest_snapshot()
    if not snap:
        return jsonify({"success": False, "error": "No snapshots found"})
    return jsonify(snap)


@app.route("/api/snapshot/<int:snapshot_id>/clients", methods=["GET"])
def api_snapshot_clients(snapshot_id):
    """Return clients for a specific snapshot, optionally filtered by referrer."""
    referrer = _get_referrer_from_request()
    clients = get_clients_by_snapshot(snapshot_id, referrer=referrer)
    return jsonify(clients)


@app.route("/api/client/<account>/history", methods=["GET"])
def api_client_history(account):
    """Return monthly history for a single client."""
    referrer = _get_referrer_from_request()
    history = get_client_monthly_history(account)
    # Filter by referrer if specified
    if referrer:
        history = [h for h in history if h.get("referred_by") == referrer]
    return jsonify(history)


@app.route("/api/fetch-api3", methods=["POST"])
def api_fetch_api3():
    """Fetch latest data from API 3 and return preview."""
    url = get_setting("api3_url", DEFAULT_API_URLS["api3"])
    data = api3_read(url)
    if isinstance(data, dict) and data.get("success") is False:
        return jsonify(data)
    if not isinstance(data, list):
        return jsonify({"success": False, "error": "Unexpected response"})
    return jsonify({"success": True, "count": len(data), "records": data})


@app.route("/api/save-snapshot", methods=["POST"])
def api_save_snapshot():
    """Save a new monthly snapshot from API 3 data.
    Computes client statuses by comparing with previous snapshot."""
    data = request.get_json() or {}
    month_label = data.get("month_label", datetime.utcnow().strftime("%Y-%m"))
    records = data.get("records", [])

    if not records:
        return jsonify({"success": False, "error": "No records provided"})

    # Save raw JSON first
    snapshot_id = create_snapshot(month_label, json.dumps(records))

    # Get previous snapshot for comparison
    prev_snap = get_latest_snapshot()
    prev_clients = {}
    if prev_snap and prev_snap["id"] != snapshot_id:
        for c in get_clients_by_snapshot(prev_snap["id"]):
            prev_clients[str(c.get("account", ""))] = c

    # Compute status for each record and enrich
    enriched_records = []
    for record in records:
        account = str(record.get("account", ""))
        prev = prev_clients.get(account)
        status = detect_status(record, prev)
        enriched = dict(record)
        enriched["status"] = status
        enriched_records.append(enriched)

    # Save flattened client records with computed statuses
    save_client_records(snapshot_id, enriched_records)

    # Update client history tracking
    from database import upsert_client_history, update_client_last_seen
    for record in enriched_records:
        account = str(record.get("account", ""))
        if account not in prev_clients:
            # New client - first time seen
            upsert_client_history(account, snapshot_id, datetime.utcnow().isoformat())
        else:
            # Existing client - update last seen
            update_client_last_seen(account, snapshot_id, datetime.utcnow().isoformat())

    # Generate comparison stats
    comparison = None
    if prev_clients:
        comparison = compare_snapshots(enriched_records, list(prev_clients.values()))

    return jsonify({
        "success": True,
        "snapshot_id": snapshot_id,
        "month_label": month_label,
        "records_saved": len(enriched_records),
        "new_clients": comparison["new_count"] if comparison else 0,
        "removed_clients": comparison["removed_count"] if comparison else 0,
        "changed_clients": comparison["changed_count"] if comparison else 0,
    })


@app.route("/api/filter-clients", methods=["GET"])
def api_filter_clients():
    """Advanced combinable filter for clients in latest snapshot, filtered by referrer."""
    referrer = _get_referrer_from_request()
    snap = get_latest_snapshot()
    if not snap:
        return jsonify({"success": False, "error": "No snapshots found"})
    clients = get_clients_by_snapshot(snap["id"], referrer=referrer)

    # Query params
    status = request.args.get("status", "")
    deposit_min = request.args.get("deposit_min", "")
    deposit_max = request.args.get("deposit_max", "")
    pnl_min = request.args.get("pnl_min", "")
    pnl_max = request.args.get("pnl_max", "")
    balance_min = request.args.get("balance_min", "")
    balance_max = request.args.get("balance_max", "")
    commission_min = request.args.get("commission_min", "")
    search = request.args.get("search", "").lower().strip()

    filtered = []
    for c in clients:
        if status and c.get("status") != status:
            continue
        if deposit_min and (c.get("deposit") or 0) < float(deposit_min):
            continue
        if deposit_max and (c.get("deposit") or 0) > float(deposit_max):
            continue
        if pnl_min and (c.get("pnl") or 0) < float(pnl_min):
            continue
        if pnl_max and (c.get("pnl") or 0) > float(pnl_max):
            continue
        if balance_min and (c.get("balance") or 0) < float(balance_min):
            continue
        if balance_max and (c.get("balance") or 0) > float(balance_max):
            continue
        if commission_min and (c.get("commission") or 0) < float(commission_min):
            continue
        if search:
            name = (c.get("fullName") or "").lower()
            account = (c.get("account") or "").lower()
            email = (c.get("email") or "").lower()
            if search not in name and search not in account and search not in email:
                continue
        filtered.append(c)

    return jsonify({"success": True, "clients": filtered, "count": len(filtered)})


@app.route("/api/referrers", methods=["GET"])
def api_referrers():
    """Return available referrer options."""
    return jsonify(REFERRER_OPTIONS)


@app.route("/api/sync-api2", methods=["POST"])
def api_sync_api2():
    """Enhanced sync: detect NEW clients from API 3 + ALL field changes for existing clients.
    Dry-run preview if dry_run=true (default). Executes only if dry_run=false."""
    data = request.get_json() or {}
    referrer = data.get("referrer")
    dry_run = data.get("dry_run", True)  # Default SAFE: preview only

    if not referrer:
        return jsonify({"success": False, "error": "Referrer required"})

    referrer_norm = str(referrer).strip().lower()

    # ── 1. Read API 2 (all clients) ──
    api2_url = get_setting("api2_url", DEFAULT_API_URLS["api2"])
    api2_data = api12_read(api2_url)
    if isinstance(api2_data, dict) and api2_data.get("success") is False:
        return jsonify({"success": False, "error": "Failed to read API 2: " + api2_data.get("error", "Unknown")})
    if not isinstance(api2_data, list):
        return jsonify({"success": False, "error": "Unexpected API 2 response"})

    # ── 2. Read API 3 — ALWAYS live (sync must detect current changes) ──
    api3_url = get_setting("api3_url", DEFAULT_API_URLS["api3"])
    api3_data = api3_read(api3_url)
    if isinstance(api3_data, dict) and api3_data.get("success") is False:
        return jsonify({"success": False, "error": "Failed to read API 3: " + api3_data.get("error", "Unknown")})
    if not isinstance(api3_data, list):
        return jsonify({"success": False, "error": "Unexpected API 3 response"})

    # ── 3. Build lookups by account ──
    api2_by_account = {}
    for r in api2_data:
        account = str(r.get("Account Id", "")).strip()
        if account:
            api2_by_account[account] = r

    api3_by_account = {}
    for r in api3_data:
        account = str(r.get("account", "")).strip()
        if account:
            api3_by_account[account] = r

    # ── 4. Filter API 3 by referrer — only keep accounts that exist in API 2 with matching referrer ──
    # Get accounts in API 2 that belong to selected referrer
    api2_accounts_for_referrer = set()
    for account, api2_rec in api2_by_account.items():
        ref_val = str(api2_rec.get("Referred by", "")).strip().lower()
        if ref_val == referrer_norm:
            api2_accounts_for_referrer.add(account)

    # ── 5. Detect NEW clients (in API 3 but NOT in API 2 at all) ──
    new_clients = []
    for account, api3_rec in api3_by_account.items():
        if account not in api2_by_account:
            new_clients.append({
                "account": account,
                "fullName": api3_rec.get("fullName", ""),
                "email": api3_rec.get("email", ""),
                "deposit": api3_rec.get("deposit"),
                "balance": api3_rec.get("balance"),
            })

    # ── 6. Detect CHANGED clients (only for selected referrer) ──
    # Field mapping: API-2-column-name → (API-3-field-name, label)
    FIELD_MAP = {
        "Student Name": ("fullName", "Student Name"),
        "Mail Id": ("email", "Mail Id"),
        "Deposit": ("deposit", "Deposit"),
        "Current Balance": ("balance", "Current Balance"),
        "Active/Inactive": ("balance", "Active/Inactive"),  # derived from balance
    }

    def _values_differ(old_val, new_val):
        """Check if two values are meaningfully different."""
        if old_val is None and new_val is None:
            return False
        if old_val is None or new_val is None:
            return True
        try:
            o = float(old_val)
            n = float(new_val)
            return abs(o - n) > 0.001
        except (ValueError, TypeError):
            return str(old_val) != str(new_val)

    changed_clients = []

    for account in api2_accounts_for_referrer:
        api2_rec = api2_by_account[account]
        api3_rec = api3_by_account.get(account)

        if not api3_rec:
            continue

        field_changes = []
        for api2_col, (api3_field, label) in FIELD_MAP.items():
            if api2_col == "Active/Inactive":
                old_val = str(api2_rec.get(api2_col, "")).strip()
                new_val = _balance_to_active_inactive(api3_rec.get("balance"))
                old_norm = old_val.lower()
                if old_norm not in ("active", "inactive"):
                    old_norm = "active" if old_norm.startswith("act") else "inactive"
                if old_norm != new_val.lower():
                    field_changes.append({
                        "field": label,
                        "api2_field": api2_col,
                        "old": api2_rec.get(api2_col),
                        "new": new_val,
                    })
            else:
                old_val = api2_rec.get(api2_col)
                new_val = api3_rec.get(api3_field)
                # Rule: never overwrite an existing email in API 2
                if api2_col == "Mail Id" and old_val:
                    continue
                if _values_differ(old_val, new_val):
                    field_changes.append({
                        "field": label,
                        "api2_field": api2_col,
                        "old": old_val,
                        "new": new_val,
                    })

        if field_changes:
            changed_clients.append({
                "account": account,
                "fullName": api2_rec.get("Student Name", api3_rec.get("fullName", "")),
                "field_changes": field_changes,
            })

    # ── 6. Execute if not dry-run ──
    add_results = []
    update_results = []

    if not dry_run:
        # Launch background sync task (one-by-one to avoid HTTP 502)
        import uuid
        task_id = str(uuid.uuid4())[:8]
        thread = threading.Thread(
            target=_run_sync_task,
            args=(task_id, referrer, api2_url, new_clients, changed_clients),
            daemon=True
        )
        thread.start()
        return jsonify({
            "success": True,
            "dry_run": False,
            "task_id": task_id,
            "total": len(new_clients) + len(changed_clients),
            "new_count": len(new_clients),
            "changed_count": len(changed_clients),
            "message": "Sync started in background. Poll /api/sync-api2/progress/" + task_id,
        })

    return jsonify({
        "success": True,
        "dry_run": dry_run,
        "referrer": referrer,
        "new_clients": new_clients,
        "new_count": len(new_clients),
        "changed_clients": changed_clients,
        "changed_count": len(changed_clients),
    })


@app.route("/api/sync-api2/progress/<task_id>")
def api_sync_api2_progress(task_id):
    """Get progress of a background sync task."""
    task = sync_tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task.get("status"),
        "total": task.get("total"),
        "done": task.get("done"),
        "error": task.get("error"),
    })


@app.route("/api/sync-sqlite-to-api2", methods=["POST"])
def api_sync_sqlite_to_api2():
    """Push local SQLite snapshot data to API 2.
    Dry-run preview if dry_run=true (default). Executes only if dry_run=false."""
    data = request.get_json() or {}
    referrer = data.get("referrer")
    snapshot_id = data.get("snapshot_id")
    dry_run = data.get("dry_run", True)  # Default SAFE: preview only

    if not referrer:
        return jsonify({"success": False, "error": "Referrer required"})
    if not snapshot_id:
        return jsonify({"success": False, "error": "Snapshot ID required"})

    referrer_norm = str(referrer).strip().lower()

    # ── 1. Read API 2 (all clients) ──
    api2_url = get_setting("api2_url", DEFAULT_API_URLS["api2"])
    api2_data = api12_read(api2_url)
    if isinstance(api2_data, dict) and api2_data.get("success") is False:
        return jsonify({"success": False, "error": "Failed to read API 2: " + api2_data.get("error", "Unknown")})
    if not isinstance(api2_data, list):
        return jsonify({"success": False, "error": "Unexpected API 2 response"})

    # Build API 2 lookup by account
    api2_by_account = {}
    for r in api2_data:
        account = str(r.get("Account Id", "")).strip()
        if account:
            api2_by_account[account] = r

    # ── 2. Read SQLite clients for snapshot + referrer ──
    sqlite_clients = get_clients_by_snapshot(snapshot_id, referrer=referrer)
    if not sqlite_clients:
        return jsonify({"success": True, "dry_run": dry_run, "referrer": referrer, "snapshot_id": snapshot_id,
                        "new_clients": [], "new_count": 0, "changed_clients": [], "changed_count": 0})

    # ── 3. Detect NEW and CHANGED clients ──
    new_clients = []
    changed_clients = []

    for c in sqlite_clients:
        account = str(c.get("account", "")).strip()
        if not account:
            continue

        if account not in api2_by_account:
            new_clients.append({
                "account": account,
                "fullName": c.get("fullName", ""),
                "email": c.get("email", ""),
                "deposit": c.get("deposit"),
                "balance": c.get("balance"),
            })
        else:
            api2_rec = api2_by_account[account]
            field_changes = []

            # Deposit
            old_deposit = api2_rec.get("Deposit")
            new_deposit = c.get("deposit")
            try:
                o = float(old_deposit) if old_deposit is not None else None
                n = float(new_deposit) if new_deposit is not None else None
                if o is None or n is None or abs(o - n) > 0.001:
                    field_changes.append({"field": "Deposit", "old": old_deposit, "new": new_deposit})
            except (ValueError, TypeError):
                if str(old_deposit) != str(new_deposit):
                    field_changes.append({"field": "Deposit", "old": old_deposit, "new": new_deposit})

            # Current Balance
            old_balance = api2_rec.get("Current Balance")
            new_balance = c.get("balance")
            try:
                o = float(old_balance) if old_balance is not None else None
                n = float(new_balance) if new_balance is not None else None
                if o is None or n is None or abs(o - n) > 0.001:
                    field_changes.append({"field": "Current Balance", "old": old_balance, "new": new_balance})
            except (ValueError, TypeError):
                if str(old_balance) != str(new_balance):
                    field_changes.append({"field": "Current Balance", "old": old_balance, "new": new_balance})

            # Active/Inactive derived from balance
            old_status = str(api2_rec.get("Active/Inactive", "")).strip().lower()
            new_status = _balance_to_active_inactive(c.get("balance"))
            if old_status not in ("active", "inactive"):
                old_status = "active" if old_status.startswith("act") else "inactive"
            if old_status != new_status.lower():
                field_changes.append({"field": "Active/Inactive", "old": api2_rec.get("Active/Inactive"), "new": new_status})

            # Never overwrite MailId if it already exists in API 2
            old_email = api2_rec.get("Mail Id")
            new_email = c.get("email")
            if old_email and new_email and old_email != new_email:
                # Skip email change — do not include in field_changes
                pass

            if field_changes:
                changed_clients.append({
                    "account": account,
                    "fullName": api2_rec.get("Student Name", c.get("fullName", "")),
                    "field_changes": field_changes,
                })

    # ── 4. Execute if not dry-run ──
    if not dry_run:
        task_id = str(uuid.uuid4())[:8]
        thread = threading.Thread(
            target=_run_sqlite_to_api2_sync_task,
            args=(task_id, api2_url, sqlite_clients, api2_by_account),
            daemon=True
        )
        thread.start()
        return jsonify({
            "success": True,
            "dry_run": False,
            "task_id": task_id,
            "total": len(new_clients) + len(changed_clients),
            "new_count": len(new_clients),
            "changed_count": len(changed_clients),
            "snapshot_id": snapshot_id,
            "referrer": referrer,
            "message": "Sync started in background. Poll /api/sync-sqlite-to-api2/progress/" + task_id,
        })

    return jsonify({
        "success": True,
        "dry_run": dry_run,
        "referrer": referrer,
        "snapshot_id": snapshot_id,
        "new_clients": new_clients,
        "new_count": len(new_clients),
        "changed_clients": changed_clients,
        "changed_count": len(changed_clients),
    })


@app.route("/api/sync-sqlite-to-api2/progress/<task_id>")
def api_sync_sqlite_to_api2_progress(task_id):
    """Get progress of a background SQLite → API 2 sync task."""
    task = sync_tasks.get(task_id)
    if not task:
        return jsonify({"success": False, "error": "Task not found"}), 404
    return jsonify({
        "success": True,
        "task_id": task_id,
        "status": task.get("status"),
        "total": task.get("total"),
        "done": task.get("done"),
        "error": task.get("error"),
    })


@app.route("/api/snapshot/<int:snapshot_id>", methods=["DELETE"])
def api_delete_snapshot(snapshot_id):
    """Delete a monthly snapshot and all related records."""
    try:
        delete_snapshot(snapshot_id)
        return jsonify({"success": True, "message": f"Snapshot {snapshot_id} deleted"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/local-backup", methods=["GET"])
def api_local_backup():
    """Download the database as an SQL dump.
    If ?month=YYYY-MM is provided, only that month's snapshot data is included.
    Token and other sensitive data are excluded."""
    import sqlite3
    import tempfile

    month_label = request.args.get("month", "").strip()
    db_path = DATABASE_PATH
    if not os.path.exists(db_path):
        return jsonify({"success": False, "error": "Database not found"}), 404

    try:
        if month_label:
            # Filtered backup: only this month's data
            from database import get_all_snapshots
            all_snaps = get_all_snapshots()
            month_snaps = [s for s in all_snaps if s.get("month_label") == month_label]
            if not month_snaps:
                return jsonify({"success": False, "error": f"No snapshots found for {month_label}"}), 404
            snapshot_ids = [s["id"] for s in month_snaps]

            # Build filtered SQL dump
            sql_content = _dump_sql(db_path, only_tables=None, snapshot_ids=snapshot_ids, exclude_keys={"dropbox_token"})
            filename = f"westernfx_{month_label}.sql"
        else:
            # Full DB dump
            sql_content = _dump_sql(db_path, only_tables=None, snapshot_ids=None, exclude_keys={"dropbox_token"})
            filename = f"westernfx_full_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.sql"

        return Response(
            sql_content,
            mimetype="application/sql",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        import traceback
        print("[local-backup error]", traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


def _dump_sql(db_path, only_tables=None, snapshot_ids=None, exclude_keys=None):
    """Return SQL text dump of a SQLite database.

    Parameters:
        db_path: path to SQLite database
        only_tables: if provided, restrict data dump to these table names
        snapshot_ids: if provided, only include rows from monthly_snapshots and
                      client_records with matching snapshot IDs, and only
                      client_history for accounts present
        exclude_keys: set of setting keys to exclude (e.g. {"dropbox_token"})
    """
    import sqlite3
    import io
    conn = sqlite3.connect(db_path)
    out = io.StringIO()

    # Write schema (tables + indexes)
    for row in conn.execute(
        "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type DESC, name"
    ).fetchall():
        obj_type, name, sql = row
        if name == "sqlite_sequence":
            continue  # Internal table — never dump its DDL
        out.write(f"{sql};\n")
    out.write("\n")

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    for (table_name,) in cursor.fetchall():
        if table_name == "sqlite_sequence":
            continue  # Never dump data for internal sequence table

        cursor.execute(f'PRAGMA table_info("{table_name}")')
        columns = [r[1] for r in cursor.fetchall()]
        if not columns:
            continue

        # Build WHERE clause
        where = ""
        params = ()
        if only_tables and table_name not in only_tables:
            continue
        if table_name == "settings" and exclude_keys:
            placeholders = ",".join("?" * len(exclude_keys))
            where = f' WHERE key NOT IN ({placeholders})'
            params = tuple(exclude_keys)
        elif snapshot_ids is not None:
            if table_name == "monthly_snapshots":
                placeholders = ",".join("?" * len(snapshot_ids))
                where = f" WHERE id IN ({placeholders})"
                params = tuple(snapshot_ids)
            elif table_name == "client_records":
                placeholders = ",".join("?" * len(snapshot_ids))
                where = f" WHERE snapshot_id IN ({placeholders})"
                params = tuple(snapshot_ids)
            elif table_name == "client_history":
                # Find accounts present in filtered client_records
                sp = ",".join("?" * len(snapshot_ids))
                acc_rows = cursor.execute(
                    f"SELECT DISTINCT account FROM client_records WHERE snapshot_id IN ({sp})",
                    tuple(snapshot_ids)
                ).fetchall()
                accounts = [r[0] for r in acc_rows]
                if not accounts:
                    continue
                ap = ",".join("?" * len(accounts))
                where = f" WHERE account IN ({ap})"
                params = tuple(accounts)
            elif table_name in ("weekly_snapshots",):
                # Exclude legacy / irrelevant tables in filtered mode
                continue

        cursor.execute(f'SELECT * FROM "{table_name}"{where}', params)
        rows = cursor.fetchall()
        if not rows:
            continue

        col_names = ",".join(f'"{c}"' for c in columns)
        out.write(f'INSERT INTO "{table_name}" ({col_names}) VALUES\n')
        lines = []
        for row in rows:
            vals = []
            for v in row:
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    escaped = str(v).replace("'", "''")
                    vals.append(f"'{escaped}'")
            lines.append("(" + ",".join(vals) + ")")
        out.write(",\n".join(lines) + ";\n\n")

    conn.close()
    return out.getvalue()


@app.route("/api/restore-sql", methods=["POST"])
def api_restore_sql():
    """Restore database from an uploaded SQL file."""
    import sqlite3
    import tempfile

    db_path = DATABASE_PATH

    if "sql_file" not in request.files:
        return jsonify({"success": False, "error": "No SQL file uploaded"}), 400

    file = request.files["sql_file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "Empty filename"}), 400

    try:
        sql_content = file.read().decode("utf-8", errors="replace")
        if not sql_content.strip():
            return jsonify({"success": False, "error": "Empty file"}), 400

        # Back up current DB
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path + ".auto_backup_" + timestamp
        if os.path.exists(db_path):
            shutil.copy2(db_path, backup_path)

        # Apply SQL to new temp DB first for safety
        data_dir = os.path.dirname(db_path)
        fd, temp_path = tempfile.mkstemp(suffix=".db", dir=data_dir)
        os.close(fd)
        try:
            conn = sqlite3.connect(temp_path)
            conn.executescript(sql_content)
            conn.commit()
            conn.close()
            # Validate it looks right (has our tables)
            conn = sqlite3.connect(temp_path)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            conn.close()
            required = {"settings", "monthly_snapshots", "client_records", "client_history"}
            if not required.issubset(set(tables)):
                os.unlink(temp_path)
                return jsonify({
                    "success": False,
                    "error": "Invalid SQL: missing required tables. Found: " + ", ".join(tables)
                }), 400

            # Replace DB
            shutil.move(temp_path, db_path)
            return jsonify({
                "success": True,
                "message": f"Database restored. Auto-backup saved at {os.path.basename(backup_path)}"
            })
        except sqlite3.Error as e:
            import traceback
            print("[restore-sql sqlite3 error]", str(e))
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            return jsonify({"success": False, "error": f"SQL error: {str(e)}"}), 400
        except Exception as e:
            import traceback
            print("[restore-sql error]", traceback.format_exc())
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            return jsonify({"success": False, "error": str(e)}), 500

    except Exception as e:
        import traceback
        print("[restore-sql outer error]", traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


# ── Cloud Backup APIs ────────────────────────────────────

@app.route("/api/dropbox-auth-url", methods=["GET"])
def api_dropbox_auth_url():
    """Get Dropbox OAuth authorization URL."""
    if get_auth_url is None:
        return jsonify({"success": False, "error": "Dropbox OAuth module not loaded"}), 500
    try:
        url = get_auth_url()
        return jsonify({"success": True, "auth_url": url})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dropbox-auth-exchange", methods=["POST"])
def api_dropbox_auth_exchange():
    """Exchange Dropbox authorization code for tokens."""
    if exchange_code is None:
        return jsonify({"success": False, "error": "Dropbox OAuth module not loaded"}), 500
    data = request.get_json() or {}
    auth_code = data.get("code")
    if not auth_code:
        return jsonify({"success": False, "error": "No authorization code provided"}), 400
    try:
        result = exchange_code(auth_code)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/dropbox-status", methods=["GET"])
def api_dropbox_status():
    """Check Dropbox OAuth connection status."""
    if test_connection is None:
        return jsonify({"success": True, "connected": False, "error": "Module not loaded"})
    result = test_connection()
    return jsonify(result)


@app.route("/api/dropbox-disconnect", methods=["POST"])
def api_dropbox_disconnect():
    """Disconnect Dropbox OAuth."""
    if disconnect_dropbox is None:
        return jsonify({"success": False, "error": "Module not loaded"}), 500
    try:
        result = disconnect_dropbox()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/backup-now", methods=["POST"])
def api_backup_now():
    """Manually trigger a backup to Dropbox."""
    result = backup()
    return jsonify(result)


@app.route("/api/backups", methods=["GET"])
def api_list_backups():
    """List available backups on Dropbox."""
    result = list_backups()
    return jsonify(result)


@app.route("/api/restore", methods=["POST"])
def api_restore():
    """Restore database from a Dropbox backup."""
    data = request.get_json() or {}
    filename = data.get("filename")
    if not filename:
        return jsonify({"success": False, "error": "No filename provided"})
    result = restore(filename)
    return jsonify(result)


@app.route("/api/backup-status", methods=["GET"])
def api_backup_status():
    """Get last backup time and status."""
    result = get_status()
    return jsonify(result)


# ── Export CSV ──
@app.route("/api/export-clients", methods=["GET"])
def api_export_clients():
    """Export clients from latest snapshot as CSV."""
    snap = get_latest_snapshot()
    if not snap:
        return jsonify({"success": False, "error": "No snapshots found"})
    clients = get_clients_by_snapshot(snap["id"])
    if not clients:
        return jsonify({"success": False, "error": "No clients in snapshot"})
    fields = ["account", "fullName", "email", "status", "deposit", "balance", "equity", "pnl", "commission", "commissionTotal"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for c in clients:
        writer.writerow({f: c.get(f, "") for f in fields})
    output.seek(0)
    label = snap.get("month_label", snap.get("week_label", "export"))
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=westernfx_clients_{label}.csv"}
    )


# ── Error Handlers ──────────────────────────────────────

@app.errorhandler(404)
def not_found(e):
    return render_template("base.html", content="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({"success": False, "error": "Internal server error"}), 500



# ── HTML Upload Parser ──────────────────────────────────────

@app.route("/api/parse-html", methods=["POST"])
def api_parse_html():
    """Upload a saved WesternFX My Traders HTML file, parse it, and return preview data."""
    if 'html_file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    
    file = request.files['html_file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Empty filename"}), 400
    
    try:
        html_content = file.read().decode('utf-8')
        traders = parse_westernfx_html(html_content)
        summary = get_summary(traders)
        return jsonify({
            "success": True,
            "traders": traders,
            "summary": summary
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



@app.route("/api/save-html-snapshot", methods=["POST"])
def api_save_html_snapshot():
    """Save parsed HTML data as a new monthly snapshot."""
    body = request.get_json(force=True, silent=True) or {}
    month_label = body.get("month_label", "").strip()
    traders = body.get("traders", [])
    
    if not month_label:
        return jsonify({"success": False, "error": "Month label required"})
    if not traders:
        return jsonify({"success": False, "error": "No trader data to save"})
    
    try:
        snap_id = create_snapshot(month_label)
        raw_json = json.dumps(traders)
        save_client_records(snap_id, traders, raw_json)
        return jsonify({"success": True, "snapshot_id": snap_id, "month_label": month_label})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
