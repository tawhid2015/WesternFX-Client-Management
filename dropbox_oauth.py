"""Dropbox OAuth 2.0 with PKCE and auto-refresh.

Credentials stored at:
    data/dropbox_oauth_credentials.json  (app_key, app_secret, redirect_uri)

Tokens stored at:
    data/dropbox_oauth_token.json  (access_token, refresh_token)

Usage:
    token = get_access_token()   # auto-refreshes if expired
"""
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
import base64
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_PATH = os.path.join(BASE_DIR, "data", "dropbox_oauth_credentials.json")
TOKEN_PATH = os.path.join(BASE_DIR, "data", "dropbox_oauth_token.json")

# ── Load Credentials ──────────────────────────────────────


def _load_creds():
    if not os.path.exists(CREDS_PATH):
        raise FileNotFoundError("Dropbox OAuth credentials not found.")
    with open(CREDS_PATH, "r") as f:
        return json.load(f)


# ── PKCE Helpers ──────────────────────────────────────────


def _generate_pkce():
    code_verifier = base64.urlsafe_b64encode(
        secrets.token_bytes(64)
    ).decode("ascii").rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        _sha256(code_verifier.encode())
    ).decode("ascii").rstrip("=")
    return code_verifier, code_challenge


def _sha256(data):
    import hashlib
    return hashlib.sha256(data).digest()


# ── Token Storage ─────────────────────────────────────────


def _load_token():
    if not os.path.exists(TOKEN_PATH):
        return None
    with open(TOKEN_PATH, "r") as f:
        return json.load(f)


def _save_token(access_token, refresh_token, expires_in=None, account_id=None):
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "created_at": datetime.utcnow().isoformat(),
        "expires_in": expires_in,
        "account_id": account_id,
    }
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)


def _update_access_token(new_access_token):
    data = _load_token()
    if data:
        data["access_token"] = new_access_token
        data["created_at"] = datetime.utcnow().isoformat()
        with open(TOKEN_PATH, "w") as f:
            json.dump(data, f, indent=2)


# ── Auth URL ──────────────────────────────────────────────


def get_auth_url():
    """Generate the Dropbox OAuth authorization URL with PKCE."""
    creds = _load_creds()
    app_key = creds["app_key"]

    code_verifier, code_challenge = _generate_pkce()
    # Store code_verifier temporarily in token file (we'll replace it after exchange)
    with open(TOKEN_PATH, "w") as f:
        json.dump({"__code_verifier": code_verifier}, f)

    params = {
        "client_id": app_key,
        "response_type": "code",
        "redirect_uri": creds.get("redirect_uri", "http://localhost"),
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "token_access_type": "offline",
    }

    url = "https://www.dropbox.com/oauth2/authorize?" + urllib.parse.urlencode(params)
    return url


# ── Token Exchange ────────────────────────────────────────


def exchange_code(auth_code):
    """Exchange authorization code for access + refresh tokens."""
    creds = _load_creds()
    app_key = creds["app_key"]
    app_secret = creds["app_secret"]
    redirect_uri = creds.get("redirect_uri", "http://localhost")

    # Retrieve the code_verifier we stored
    temp = _load_token() or {}
    code_verifier = temp.pop("__code_verifier", None)

    if not code_verifier:
        raise RuntimeError("Code verifier not found. Start authorization from the beginning.")

    # Build Basic auth header
    auth_str = f"{app_key}:{app_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()

    data = urllib.parse.urlencode({
        "code": auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }).encode()

    req = urllib.request.Request(
        "https://api.dropboxapi.com/oauth2/token",
        data=data,
        headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    access_token = result.get("access_token")
    refresh_token = result.get("refresh_token")
    expires_in = result.get("expires_in")
    account_id = result.get("account_id")

    if not access_token or not refresh_token:
        raise RuntimeError(f"Token exchange failed: {result}")

    _save_token(access_token, refresh_token, expires_in, account_id)

    return {"success": True, "message": "Dropbox connected successfully."}


# ── Refresh Token ─────────────────────────────────────────


def _refresh_access_token():
    """Use refresh token to get a new access token."""
    creds = _load_creds()
    app_key = creds["app_key"]
    app_secret = creds["app_secret"]

    token_data = _load_token()
    if not token_data or not token_data.get("refresh_token"):
        raise RuntimeError("No refresh token available. Please re-authorize.")

    refresh_token = token_data["refresh_token"]

    auth_str = f"{app_key}:{app_secret}"
    auth_b64 = base64.b64encode(auth_str.encode()).decode()

    data = urllib.parse.urlencode({
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode()

    req = urllib.request.Request(
        "https://api.dropboxapi.com/oauth2/token",
        data=data,
        headers={"Authorization": f"Basic {auth_b64}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    new_access_token = result.get("access_token")
    new_refresh_token = result.get("refresh_token")
    expires_in = result.get("expires_in")

    if not new_access_token:
        raise RuntimeError(f"Token refresh failed: {result}")

    # Update token file with new access token
    # Some responses also include a new refresh token — save it too
    with open(TOKEN_PATH, "r") as f:
        data = json.load(f)
    data["access_token"] = new_access_token
    data["created_at"] = datetime.utcnow().isoformat()
    if expires_in:
        data["expires_in"] = expires_in
    if new_refresh_token:
        data["refresh_token"] = new_refresh_token
    with open(TOKEN_PATH, "w") as f:
        json.dump(data, f, indent=2)

    return new_access_token


# ── Get Valid Access Token (with auto-refresh) ────────────


def get_access_token():
    """Return a valid access token, auto-refreshing if expired."""
    token_data = _load_token()
    if not token_data:
        raise RuntimeError("Not authenticated. Please connect Dropbox in Settings.")

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    created_at_str = token_data.get("created_at")
    expires_in = token_data.get("expires_in")

    if not access_token or not refresh_token:
        raise RuntimeError("Incomplete token data. Please re-authorize.")

    # Check if token might be expired (Dropbox tokens typically last 4 hours)
    if created_at_str and expires_in:
        created_at = datetime.fromisoformat(created_at_str)
        now = datetime.utcnow()
        elapsed = (now - created_at).total_seconds()
        # Refresh if expired or about to expire in 5 minutes
        if elapsed >= expires_in - 300:
            return _refresh_access_token()

    return access_token


# ── Test Connection ───────────────────────────────────────


def test_connection():
    """Test if Dropbox OAuth is connected and valid."""
    token_data = _load_token()
    if not token_data:
        return {"success": True, "connected": False, "error": "Not connected"}

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    if not access_token or not refresh_token:
        return {"success": True, "connected": False, "error": "Incomplete credentials"}

    try:
        # Test with a simple API call
        req = urllib.request.Request(
            "https://api.dropboxapi.com/2/users/get_current_account",
            data=b'null',
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            account = json.loads(resp.read())
            return {
                "success": True,
                "connected": True,
                "name": account.get("name", {}).get("display_name", ""),
                "email": account.get("email", ""),
            }
    except Exception as e:
        # Try refreshing once
        try:
            new_token = _refresh_access_token()
            req = urllib.request.Request(
                "https://api.dropboxapi.com/2/users/get_current_account",
                data=b'null',
                headers={"Authorization": f"Bearer {new_token}", "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                account = json.loads(resp.read())
                return {
                    "success": True,
                    "connected": True,
                    "name": account.get("name", {}).get("display_name", ""),
                    "email": account.get("email", ""),
                }
        except Exception:
            return {"success": True, "connected": False, "error": str(e)}


# ── Disconnect ────────────────────────────────────────────


def disconnect():
    """Remove stored tokens (disconnect Dropbox)."""
    if os.path.exists(TOKEN_PATH):
        os.remove(TOKEN_PATH)
    return {"success": True, "message": "Dropbox disconnected."}
