"""Self-update: check GitHub for a newer version and download it.

The app reads a small `version.json` published on GitHub. If the version there
is newer than this build, the UI offers to download + install the new release.
Downloads happen via Python (urllib), so the file is NOT quarantined by macOS
and the user won't hit the "unidentified developer / damaged" Gatekeeper wall.
"""

import os
import json
import ssl
import subprocess
import urllib.request

from .config import APP_VERSION, UPDATE_MANIFEST_URL

try:
    import certifi
    _CA_FILE = certifi.where()
except Exception:
    _CA_FILE = None


def _ssl_context():
    if _CA_FILE:
        return ssl.create_default_context(cafile=_CA_FILE)
    return ssl.create_default_context()


def _version_tuple(v):
    """Turn '1.2.10' into (1, 2, 10) for correct numeric comparison."""
    parts = []
    for piece in str(v or "0").strip().split("."):
        digits = "".join(ch for ch in piece if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def _is_newer(remote, local):
    return _version_tuple(remote) > _version_tuple(local)


def fetch_manifest(timeout=10):
    req = urllib.request.Request(UPDATE_MANIFEST_URL, headers={"User-Agent": "FinlandSchedule"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update():
    """Return a dict describing whether an update is available.

    Never raises — on any error it reports update_available=False so the app
    keeps working offline.
    """
    result = {
        "current_version": APP_VERSION,
        "latest_version": APP_VERSION,
        "update_available": False,
        "notes": "",
        "download_url": "",
        "error": "",
    }
    try:
        data = fetch_manifest()
        latest = str(data.get("version", "")).strip()
        result["latest_version"] = latest or APP_VERSION
        result["notes"] = data.get("notes", "") or ""
        result["download_url"] = data.get("download_url", "") or ""
        result["update_available"] = bool(latest) and _is_newer(latest, APP_VERSION)
    except Exception as e:  # offline, bad JSON, 404, etc. — stay silent
        result["error"] = str(e)
    return result


def download_and_open(download_url, timeout=120):
    """Download the new .dmg via Python (no quarantine) and open it in Finder."""
    if not download_url:
        raise ValueError("No download URL")
    dest_dir = os.path.expanduser("~/Downloads")
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, "Finland Schedule Update.dmg")
    req = urllib.request.Request(download_url, headers={"User-Agent": "FinlandSchedule"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp, open(dest, "wb") as f:
        f.write(resp.read())
    # Open the .dmg so the user can drag the new app into Applications.
    subprocess.run(["open", dest], check=False)
    return dest
