"""
WesternFX IB Management Tool — Google Apps Script API Client
=================================================================
Wrapper for all 3 GAS Web App APIs. Handles GET requests,
URL encoding, error handling, and response parsing.
"""
import requests
from urllib.parse import urlencode, quote
from config import API_SHEET_NAME, API_TIMEOUT_SECONDS


def _build_url(base_url, params):
    """Build a full URL with query parameters.
    Uses %20 for spaces (not +) because + in parameter keys is treated literally by GAS.
    """
    # Ensure base URL has no trailing query params already
    separator = "&" if "?" in base_url else "?"
    # Manually encode each param: keys use %20 for spaces, values use standard urlencode
    parts = []
    for key, value in params.items():
        # Encode key: replace spaces with %20
        encoded_key = quote(str(key), safe="")
        # Encode value: standard URL encoding (spaces as +)
        if value is None:
            encoded_val = ""
        else:
            encoded_val = quote(str(value), safe="")
        parts.append(f"{encoded_key}={encoded_val}")
    query = "&".join(parts)
    return f"{base_url}{separator}{query}"


def _safe_get(url, timeout=API_TIMEOUT_SECONDS):
    """Perform a safe GET request and return parsed JSON or error dict."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data
    except requests.exceptions.Timeout:
        return {"success": False, "error": "Request timed out"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Connection error"}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"HTTP error: {e.response.status_code}"}
    except requests.exceptions.JSONDecodeError:
        return {"success": False, "error": "Invalid JSON response"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def test_api(base_url):
    """Quick connectivity test — perform a READ request."""
    params = {"action": "read", "path": API_SHEET_NAME}
    url = _build_url(base_url, params)
    data = _safe_get(url)
    if isinstance(data, list):
        return {"success": True, "records": len(data)}
    if isinstance(data, dict) and data.get("success") is False:
        return {"success": False, "error": data.get("error", "Unknown error")}
    return {"success": False, "error": "Unexpected response format"}


# ──────────────────────────────────────────────────────────
# API 1 / API 2 — Student Records (14-column schema)
# ──────────────────────────────────────────────────────────

def api12_read(base_url):
    """Read all student records from API 1 or API 2.
    Returns: list of student dicts or error dict.
    """
    params = {"action": "read", "path": API_SHEET_NAME}
    url = _build_url(base_url, params)
    data = _safe_get(url)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data  # error dict
    return {"success": False, "error": "Unexpected response format"}


def api12_add(base_url, student_data):
    """Add a new student record.
    student_data: dict with keys matching API parameters.
    Required: AccountId OR MobileNo.
    """
    params = {"action": "write", "path": API_SHEET_NAME}
    params.update(student_data)
    url = _build_url(base_url, params)
    return _safe_get(url)


def api12_update(base_url, identifier, changed_fields):
    """Partial update of an existing student record.
    identifier: dict with 'AccountId' and/or 'MobileNo'
    changed_fields: dict of ONLY the fields to change.
    """
    params = {"action": "update", "path": API_SHEET_NAME}
    params.update(identifier)
    params.update(changed_fields)
    url = _build_url(base_url, params)
    return _safe_get(url)


# ──────────────────────────────────────────────────────────
# API 3 — Trading Account Data (9-column schema)
# ──────────────────────────────────────────────────────────

def api3_read(base_url):
    """Read all account records from API 3.
    Returns: list of account dicts or error dict.
    """
    params = {"action": "read", "path": API_SHEET_NAME}
    url = _build_url(base_url, params)
    data = _safe_get(url)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data
    return {"success": False, "error": "Unexpected response format"}


def api3_add(base_url, account_data):
    """Add a new account record to API 3.
    Required: account (as string).
    """
    params = {"action": "write", "path": API_SHEET_NAME}
    params.update(account_data)
    url = _build_url(base_url, params)
    return _safe_get(url)


def api3_update(base_url, account, changed_fields):
    """Partial update of an existing account record in API 3.
    account: string account identifier
    changed_fields: dict of ONLY the fields to change.
    """
    params = {"action": "update", "path": API_SHEET_NAME, "account": account}
    params.update(changed_fields)
    url = _build_url(base_url, params)
    return _safe_get(url)
