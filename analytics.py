"""
WesternFX IB Management Tool — Analytics & Status Detection
===============================================================
Computes client statuses, KPIs, and comparisons between snapshots.
"""
import json
from collections import defaultdict

from config import (
    STATUS_ACTIVE,
    STATUS_INACTIVE,
    STATUS_NEW,
    STATUS_NEWLY_ACTIVE,
    STATUS_NEWLY_INACTIVE,
    STATUS_DORMANT,
    STATUS_DISAPPEARED,
)


# ── Status Detection ────────────────────────────────────

def detect_status(record, previous_record=None):
    """Simple status: Balance > 0 = ACTIVE, Balance <= 0 = INACTIVE."""
    balance = _float(record.get("balance", 0))
    if balance > 0:
        return STATUS_ACTIVE
    return STATUS_INACTIVE


def compute_snapshot_stats(clients):
    """Compute KPI statistics for a snapshot.
    ACTIVE:  balance > 0
    INACTIVE: balance <= 0
    PROFITABLE: balance > deposit
    BLOWN: deposit > 0 and balance <= 0
    """
    total = len(clients)
    active = sum(1 for c in clients if _float(c.get("balance", 0)) > 0)
    inactive = sum(1 for c in clients if _float(c.get("balance", 0)) <= 0)
    profitable = sum(1 for c in clients if _float(c.get("balance", 0)) > _float(c.get("deposit", 0)))
    blown = sum(1 for c in clients if _float(c.get("deposit", 0)) > 0 and _float(c.get("balance", 0)) <= 0)

    total_deposit = sum(_float(c.get("deposit", 0)) for c in clients)
    total_commission = sum(_float(c.get("commission", 0)) for c in clients)
    total_commission_total = sum(_float(c.get("commissionTotal", 0)) for c in clients)
    total_balance = sum(_float(c.get("balance", 0)) for c in clients)
    total_equity = sum(_float(c.get("equity", 0)) for c in clients)

    # Profitable client profit = sum(balance - deposit) for clients where balance > deposit
    profitable_profit = sum(
        _float(c.get("balance", 0)) - _float(c.get("deposit", 0))
        for c in clients
        if _float(c.get("balance", 0)) > _float(c.get("deposit", 0))
    )

    # Blown accounts = deposit > 0 but balance <= 0
    blown_accounts = [
        {
            "account": c.get("account", ""),
            "fullName": c.get("fullName", ""),
            "deposit": round(_float(c.get("deposit", 0)), 2),
            "balance": round(_float(c.get("balance", 0)), 2),
        }
        for c in clients
        if _float(c.get("deposit", 0)) > 0 and _float(c.get("balance", 0)) <= 0
    ]

    # Profitable clients detail (for highlights)
    profitable_clients = [
        {
            "account": c.get("account", ""),
            "fullName": c.get("fullName", ""),
            "deposit": round(_float(c.get("deposit", 0)), 2),
            "balance": round(_float(c.get("balance", 0)), 2),
            "profit": round(_float(c.get("balance", 0)) - _float(c.get("deposit", 0)), 2),
        }
        for c in clients
        if _float(c.get("balance", 0)) > _float(c.get("deposit", 0))
    ]

    zero_deposit = sum(1 for c in clients if _float(c.get("deposit", 0)) == 0)

    return {
        "total_clients": total,
        "active": active,
        "inactive": inactive,
        "profitable": profitable,
        "blown": blown,
        "blown_accounts": blown_accounts,
        "profitable_profit": round(profitable_profit, 2),
        "profitable_clients": profitable_clients,
        "zero_deposit": zero_deposit,
        "total_deposit": round(total_deposit, 2),
        "total_commission": round(total_commission, 2),
        "total_commission_total": round(total_commission_total, 2),
        "total_balance": round(total_balance, 2),
        "total_equity": round(total_equity, 2),
    }


def compare_snapshots(current_clients, previous_clients):
    """Compare two snapshots and generate change reports."""
    prev_by_account = {str(c.get("account", "")): c for c in previous_clients}
    curr_by_account = {str(c.get("account", "")): c for c in current_clients}

    new_accounts = []
    removed_accounts = []
    changed = []

    for account, curr in curr_by_account.items():
        if account not in prev_by_account:
            new_accounts.append({
                "account": account,
                "fullName": curr.get("fullName", ""),
                "status": STATUS_NEW,
            })
            continue

        prev = prev_by_account[account]
        changes = _compute_changes(prev, curr)
        if changes:
            changed.append({
                "account": account,
                "fullName": curr.get("fullName", ""),
                "changes": changes,
                "status": curr.get("status", ""),
                "previous_status": prev.get("status", ""),
            })

    for account, prev in prev_by_account.items():
        if account not in curr_by_account:
            removed_accounts.append({
                "account": account,
                "fullName": prev.get("fullName", ""),
                "status": STATUS_DISAPPEARED,
            })

    return {
        "new_accounts": new_accounts,
        "removed_accounts": removed_accounts,
        "changed": changed,
        "new_count": len(new_accounts),
        "removed_count": len(removed_accounts),
        "changed_count": len(changed),
    }


# ── Internal Helpers ─────────────────────────────────────

def _float(value):
    if value is None or value == "" or value == "N/A":
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _compute_changes(prev, curr):
    """Compute field-by-field changes between two client records."""
    changes = {}
    fields = ["equity", "balance", "pnl", "deposit", "commission", "commissionTotal"]
    for field in fields:
        prev_val = _float(prev.get(field, 0))
        curr_val = _float(curr.get(field, 0))
        if prev_val != curr_val:
            changes[field] = {
                "previous": prev_val,
                "current": curr_val,
                "change": round(curr_val - prev_val, 2),
                "percent": round(((curr_val - prev_val) / prev_val * 100), 2) if prev_val != 0 else None,
            }
    return changes
