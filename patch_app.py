#!/usr/bin/env python3
"""
Patch script to update app.py for the new Snapshot → API 2 Sync feature.
"""

import re

APP_PY = "/home/node/.openclaw/workspace/westernfx-ib-tool/app.py"

with open(APP_PY, "r", encoding="utf-8") as f:
    content = f.read()

# ── 1. Replace api_sync_sqlite_to_api2 endpoint ──
OLD_ENDPOINT = '''@app.route("/api/sync-sqlite-to-api2", methods=["POST"])
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
    })'''

NEW_ENDPOINT = '''@app.route("/api/sync-sqlite-to-api2", methods=["POST"])
def api_sync_sqlite_to_api2():
    """Push local SQLite snapshot data to API 2.
    Dry-run preview if dry_run=true (default). Executes only if dry_run=false.

    Matching logic:
    1. Read API 2, filter to only clients with selected referrer.
    2. Read SQLite snapshot clients for selected snapshot + referrer.
    3. Match by account (Account Id ↔ account).
    4. New: account in SQLite but NOT in filtered API 2.
    5. Update: account in both, any field differs.
    6. Unchanged: account in both, all fields identical.

    Snapshot → API 2 field mapping:
      fullName → Student Name
      email → Mail Id
      account → Account Id
      deposit → Deposit
      balance → Current Balance
      balance>0 → Active, balance≤0 → Inactive
    """
    data = request.get_json() or {}
    referrer = data.get("referrer")
    snapshot_id = data.get("snapshot_id")
    dry_run = data.get("dry_run", True)  # Default SAFE: preview only

    if not referrer:
        return jsonify({"success": False, "error": "Referrer required"})
    if not snapshot_id:
        return jsonify({"success": False, "error": "Snapshot ID required"})

    referrer_norm = str(referrer).strip().lower()

    # ── 1. Read API 2 and filter by referrer ──
    api2_url = get_setting("api2_url", DEFAULT_API_URLS["api2"])
    api2_data = api12_read(api2_url)
    if isinstance(api2_data, dict) and api2_data.get("success") is False:
        return jsonify({"success": False, "error": "Failed to read API 2: " + api2_data.get("error", "Unknown")})
    if not isinstance(api2_data, list):
        return jsonify({"success": False, "error": "Unexpected API 2 response"})

    # Filter API 2 to only clients with matching referrer (case-insensitive)
    api2_by_account = {}
    for r in api2_data:
        rec_referrer = str(r.get("Referred by", "")).strip().lower()
        if rec_referrer == referrer_norm:
            account = str(r.get("Account Id", "")).strip()
            if account:
                api2_by_account[account] = r

    # ── 2. Read SQLite clients for snapshot + referrer ──
    sqlite_clients = get_clients_by_snapshot(snapshot_id, referrer=referrer)
    if not sqlite_clients:
        return jsonify({
            "success": True,
            "dry_run": dry_run,
            "referrer": referrer,
            "snapshot_id": snapshot_id,
            "new_clients": [],
            "new_count": 0,
            "changed_clients": [],
            "changed_count": 0,
            "unchanged_clients": [],
            "unchanged_count": 0,
        })

    # ── 3. Detect NEW, CHANGED, and UNCHANGED clients ──
    new_clients = []
    changed_clients = []
    unchanged_clients = []

    for c in sqlite_clients:
        account = str(c.get("account", "")).strip()
        if not account:
            continue

        if account not in api2_by_account:
            # NEW client — not in API 2 for this referrer
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

            # Student Name (fullName)
            old_name = api2_rec.get("Student Name")
            new_name = c.get("fullName")
            if _values_differ(old_name, new_name):
                field_changes.append({
                    "field": "Student Name",
                    "old": old_name,
                    "new": new_name,
                })

            # Mail Id (email) — compare for preview, but NEVER update existing
            old_email = api2_rec.get("Mail Id")
            new_email = c.get("email")
            if _values_differ(old_email, new_email):
                field_changes.append({
                    "field": "Mail Id",
                    "old": old_email,
                    "new": new_email,
                    "note": "Will not overwrite existing email",
                })

            # Deposit
            old_deposit = api2_rec.get("Deposit")
            new_deposit = c.get("deposit")
            if _numeric_differ(old_deposit, new_deposit):
                field_changes.append({
                    "field": "Deposit",
                    "old": old_deposit,
                    "new": new_deposit,
                })

            # Current Balance
            old_balance = api2_rec.get("Current Balance")
            new_balance = c.get("balance")
            if _numeric_differ(old_balance, new_balance):
                field_changes.append({
                    "field": "Current Balance",
                    "old": old_balance,
                    "new": new_balance,
                })

            # Active/Inactive derived from balance
            old_status_raw = str(api2_rec.get("Active/Inactive", "")).strip()
            old_status = old_status_raw.lower()
            if old_status not in ("active", "inactive"):
                old_status = "active" if old_status.startswith("act") else "inactive"
            new_status = _balance_to_active_inactive(c.get("balance"))
            if old_status != new_status.lower():
                field_changes.append({
                    "field": "Active/Inactive",
                    "old": old_status_raw,
                    "new": new_status,
                })

            if field_changes:
                changed_clients.append({
                    "account": account,
                    "fullName": api2_rec.get("Student Name", c.get("fullName", "")),
                    "field_changes": field_changes,
                })
            else:
                unchanged_clients.append({
                    "account": account,
                    "fullName": api2_rec.get("Student Name", c.get("fullName", "")),
                })

    # ── 4. Execute if not dry-run ──
    if not dry_run:
        task_id = str(uuid.uuid4())[:8]
        thread = threading.Thread(
            target=_run_sqlite_to_api2_sync_task,
            args=(task_id, api2_url, sqlite_clients, api2_by_account, referrer),
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
            "unchanged_count": len(unchanged_clients),
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
        "unchanged_clients": unchanged_clients,
        "unchanged_count": len(unchanged_clients),
    })'''

if OLD_ENDPOINT not in content:
    print("ERROR: Could not find old endpoint in app.py")
    exit(1)

content = content.replace(OLD_ENDPOINT, NEW_ENDPOINT)

# ── 2. Replace _run_sqlite_to_api2_sync_task ──
OLD_TASK_START = '''def _run_sqlite_to_api2_sync_task(task_id, api2_url, sqlite_clients, api2_by_account):
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
                
                results.append({'''

old_task_end_marker = '''        sync_tasks[task_id]["status"] = "done"
    except Exception as e:
        sync_tasks[task_id] = {"status": "error", "total": 0, "done": 0, "results": [], "error": str(e)}'''

idx = content.find(OLD_TASK_START)
if idx == -1:
    print("ERROR: Could not find old task function start in app.py")
    exit(1)

end_idx = content.find(old_task_end_marker, idx)
if end_idx == -1:
    print("ERROR: Could not find old task function end in app.py")
    exit(1)

end_idx += len(old_task_end_marker)

NEW_TASK = '''def _run_sqlite_to_api2_sync_task(task_id, api2_url, sqlite_clients, api2_by_account, referrer):
    """Background thread: push SQLite snapshot clients to API 2 one by one.

    Rules:
    - New clients: add with selected referrer, Active/Inactive from balance.
    - Updates: only push fields that were identified as changed.
    - Never overwrite existing Mail Id on existing clients.
    - Never touch clients belonging to other referrers.
    """
    try:
        results = []
        all_ops = []

        # Build operation list: only for accounts in the filtered set
        for c in sqlite_clients:
            account = str(c.get("account", "")).strip()
            if not account:
                continue
            if account not in api2_by_account:
                all_ops.append(("add", c))
            else:
                all_ops.append(("update", c))

        total = len(all_ops)
        sync_tasks[task_id] = {
            "status": "running",
            "total": total,
            "done": 0,
            "results": [],
            "error": None,
        }

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
                        "ReferredBy": referrer,
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
                    if _numeric_differ(old_deposit, new_deposit):
                        changed_fields["Deposit"] = new_deposit

                    # Current Balance
                    old_balance = api2_rec.get("Current Balance")
                    new_balance = client.get("balance")
                    if _numeric_differ(old_balance, new_balance):
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
                    changed_fields.pop("StudentName", None)  # Never overwrite name on update

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
                    "account": client.get("account", "unknown"),
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
        sync_tasks[task_id] = {"status": "error", "total": 0, "done": 0, "results": [], "error": str(e)}'''

content = content[:idx] + NEW_TASK + content[end_idx:]

# ── 3. Add helper functions before _balance_to_active_inactive ──
helpers = '''
def _values_differ(old, new):
    """Check if two values differ (handles None, strings, numbers)."""
    if old is None and new is None:
        return False
    if old is None or new is None:
        return True
    return str(old).strip() != str(new).strip()


def _numeric_differ(old, new):
    """Check if two numeric values differ by more than 0.001."""
    try:
        o = float(old) if old is not None else None
        n = float(new) if new is not None else None
        if o is None or n is None:
            return o is not None or n is not None
        return abs(o - n) > 0.001
    except (ValueError, TypeError):
        return str(old) != str(new)


'''

idx_helpers = content.find("def _balance_to_active_inactive")
if idx_helpers == -1:
    print("ERROR: Could not find _balance_to_active_inactive in app.py")
    exit(1)

content = content[:idx_helpers] + helpers + content[idx_helpers:]

with open(APP_PY, "w", encoding="utf-8") as f:
    f.write(content)

print("app.py patched successfully.")
