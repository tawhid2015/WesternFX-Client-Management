"""
WesternFX IB Management Tool — Configuration
=============================================
Default settings and constants.
"""
import os

# ── Database ──────────────────────────────────────────────
DATABASE_PATH = os.path.join(os.path.dirname(__file__), "data", "westernfx.db")

# ── Default API URLs ────────────────────────────────────────
DEFAULT_API_URLS = {
    "api2": "https://script.google.com/macros/s/AKfycbxqYd0QanVEgAPNj5S4M6vQAtPavFEvhcsa6d_hgx6ip1-tZdLswLPgll17qeiqfuAx/exec",
    "api3": "https://script.google.com/macros/s/AKfycbx3av5WhEMS0MQVXXKxIdk3g6PcETmDw-Ty_sJYm3dstHD6hi2-_X_6J04O8EvQ5xw/exec",
}

# ── API Constants ───────────────────────────────────────────
API_SHEET_NAME = "Sheet1"
API_TIMEOUT_SECONDS = 30

# ── API 1/2 Column Headers (human-readable, as returned by API) ──
API12_HEADERS = [
    "SL No.",
    "Student Name",
    "Batch No.",
    "Mail Id",
    "Account Id",
    "Mobile No.",
    "Referred by",
    "Linked up",
    "Deposit",
    "Current Balance",
    "Active/Inactive",
    "D.O.J",
    "D.O.E",
    "Remarks",
]

# ── API 3 Column Headers (exact as returned by API) ─────────
API3_HEADERS = [
    "fullName",
    "email",
    "account",
    "equity",
    "balance",
    "pnl",
    "deposit",
    "commission",
    "commissionTotal",
]

# ── Referrer Options for API 2 Sync ─────────────────────────
REFERRER_OPTIONS = [
    "Tawhid Sir",
    "Pradyut Mondal",
]

# ── Status Constants ──────────────────────────────────────
STATUS_ACTIVE = "ACTIVE"
STATUS_INACTIVE = "INACTIVE"
STATUS_NEW = "NEW"
STATUS_NEWLY_ACTIVE = "NEWLY ACTIVE"
STATUS_NEWLY_INACTIVE = "NEWLY INACTIVE"
STATUS_DORMANT = "DORMANT"
STATUS_DISAPPEARED = "DISAPPEARED"


