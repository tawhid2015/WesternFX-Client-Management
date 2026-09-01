"""
WesternFX IB Management Tool — Password Protection & IP Whitelisting
==================================================================
Simple session + IP-based authentication.
"""
import os
import hashlib
import hmac
import secrets
from datetime import datetime

try:
    from database import get_db, get_setting, set_setting
except ImportError:
    # Allow import during tests without full app context
    get_db = get_setting = set_setting = None

# ── Constants ─────────────────────────────────────────────
DEFAULT_PASSWORD = "Tawhid+Pradyut"
SESSION_KEY = "auth_session_token"

# ── Password Management ─────────────────────────────────

def _hash_password(password: str) -> str:
    """Hash a password using PBKDF2."""
    salt = secrets.token_hex(16)
    phash = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return f"{salt}${phash}"

def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against its stored hash."""
    try:
        salt, phash = stored.split("$")
        check = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
        return hmac.compare_digest(phash, check)
    except Exception:
        return False

def get_stored_password_hash() -> str:
    """Get the stored password hash. Initialize with default if not set."""
    if get_setting is None:
        return _hash_password(DEFAULT_PASSWORD)
    phash = get_setting("auth_password_hash", None)
    if not phash:
        phash = _hash_password(DEFAULT_PASSWORD)
        set_setting("auth_password_hash", phash)
    return phash

def change_password(new_password: str) -> None:
    """Change the auth password."""
    phash = _hash_password(new_password)
    set_setting("auth_password_hash", phash)


def check_password(password: str) -> bool:
    """Check if a password is correct."""
    stored = get_stored_password_hash()
    return _verify_password(password, stored)


# ── IP Whitelist Management ───────────────────────────────

def _get_client_ip(request):
    """Get the real client IP, handling proxies."""
    # Railway/Cloudflare: X-Forwarded-For
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    forwarded_single = request.headers.get("X-Real-Ip", "")
    if forwarded_single:
        return forwarded_single.strip()
    return request.remote_addr or "unknown"

def get_client_ip(request):
    """Public: get the real client IP."""
    return _get_client_ip(request)

def is_ip_whitelisted(ip: str) -> bool:
    """Check if an IP address is whitelisted."""
    if get_db is None:
        return True  # During testing
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM auth_ips WHERE ip = ?", (ip,)
        ).fetchone()
        return row is not None

def whitelist_ip(ip: str) -> None:
    """Add an IP address to the whitelist."""
    if get_db is None:
        return
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO auth_ips (ip, authorized_at) VALUES (?, ?)",
            (ip, datetime.utcnow().isoformat()),
        )

def remove_whitelisted_ip(ip: str) -> None:
    """Remove an IP address from the whitelist."""
    if get_db is None:
        return
    with get_db() as conn:
        conn.execute("DELETE FROM auth_ips WHERE ip = ?", (ip,))

def get_all_whitelisted_ips():
    """Return all whitelisted IPs."""
    if get_db is None:
        return []
    with get_db() as conn:
        rows = conn.execute(
            "SELECT ip, authorized_at FROM auth_ips ORDER BY authorized_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


# ── Session Token Management ──────────────────────────────

def generate_session_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(32)

def is_session_valid(session) -> bool:
    """Check if the session contains a valid auth token."""
    token = session.get(SESSION_KEY)
    if not token:
        return False
    if not isinstance(token, str) or len(token) < 16:
        return False
    return True


def authenticate_request(request, session) -> tuple:
    """
    Check if the current request is authenticated.
    Returns: (is_authenticated: bool, client_ip: str)
    """
    client_ip = _get_client_ip(request)
    
    # Check IP whitelist first (fast path)
    if is_ip_whitelisted(client_ip):
        return True, client_ip
    
    # Check session
    if is_session_valid(session):
        # Auto-whitelist this IP on first successful session use
        whitelist_ip(client_ip)
        return True, client_ip
    
    return False, client_ip
