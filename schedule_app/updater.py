"""Self-update: check GitHub for a newer version and download it.

The app reads a small `version.json` published on GitHub. If the version there
is newer than this build, the UI offers to download + install the new release.
Downloads happen via Python (urllib), so the file is NOT quarantined by macOS
and the user won't hit the "unidentified developer / damaged" Gatekeeper wall.
"""

import os
import sys
import json
import ssl
import shlex
import shutil
import tempfile
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


def _running_app_bundle():
    """Path to the .app we're running from (…/X.app), or None."""
    p = sys.executable  # …/X.app/Contents/MacOS/X
    for _ in range(3):
        p = os.path.dirname(p)
    return p if p.endswith(".app") else None


def _install_target():
    """Where to install the update: replace where we run, else /Applications."""
    bundle = _running_app_bundle()
    if bundle and "AppTranslocation" not in bundle and os.path.isdir(bundle):
        return bundle
    return "/Applications/Finland Schedule.app"


def download_and_install(download_url, timeout=180):
    """Download the update and replace the installed app IN PLACE, then relaunch.

    Downloads via Python (no quarantine), mounts the .dmg hidden (-nobrowse so no
    desktop disk icon), then a detached helper waits for the app to quit, swaps the
    bundle, cleans up, and reopens — so there is never a second copy.
    """
    if not download_url:
        raise ValueError("No download URL")
    tmpdir = tempfile.mkdtemp(prefix="fs_update_")
    dmg = os.path.join(tmpdir, "update.dmg")
    req = urllib.request.Request(download_url, headers={"User-Agent": "FinlandSchedule"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp, open(dmg, "wb") as f:
        shutil.copyfileobj(resp, f)

    mountpoint = os.path.join(tmpdir, "mnt")
    os.makedirs(mountpoint, exist_ok=True)
    subprocess.run(["hdiutil", "attach", dmg, "-nobrowse", "-mountpoint", mountpoint],
                   check=True, capture_output=True)

    new_app = None
    for name in os.listdir(mountpoint):
        if name.endswith(".app"):
            new_app = os.path.join(mountpoint, name)
            break
    if not new_app:
        subprocess.run(["hdiutil", "detach", mountpoint, "-force"], capture_output=True)
        raise RuntimeError("No application found in the update")

    target = _install_target()
    helper = os.path.join(tmpdir, "install.sh")
    script = (
        "#!/bin/bash\n"
        "sleep 2\n"
        "pkill -f 'Finland Schedule.app/Contents/MacOS' 2>/dev/null\n"
        "sleep 2\n"
        f"if ditto {shlex.quote(new_app)} {shlex.quote(target + '.new')} ; then\n"
        f"  rm -rf {shlex.quote(target)}\n"
        f"  mv {shlex.quote(target + '.new')} {shlex.quote(target)}\n"
        f"  xattr -dr com.apple.quarantine {shlex.quote(target)} 2>/dev/null\n"
        "fi\n"
        f"hdiutil detach {shlex.quote(mountpoint)} -force 2>/dev/null\n"
        f"rm -f {shlex.quote(dmg)} 2>/dev/null\n"
        f"open {shlex.quote(target)}\n"
    )
    with open(helper, "w") as f:
        f.write(script)
    os.chmod(helper, 0o755)
    subprocess.Popen(["/bin/bash", helper], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target
