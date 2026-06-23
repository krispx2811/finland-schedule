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
import time
import shlex
import shutil
import tempfile
import threading
import subprocess
import urllib.request

from .config import APP_VERSION, UPDATE_MANIFEST_URL

# Live progress of an in-app update, polled by the UI.
_progress = {"active": False, "percent": 0, "phase": "idle", "error": "", "done": False}


def get_progress():
    return dict(_progress)


def start_update(download_url):
    """Kick off the download+install on a background thread (non-blocking)."""
    if _progress.get("active") and not _progress.get("done"):
        return  # already running
    _progress.update(active=True, percent=0, phase="starting", error="", done=False)
    threading.Thread(target=_run_update, args=(download_url,), daemon=True).start()


def _run_update(download_url):
    try:
        download_and_install(download_url)
        _progress.update(phase="installing", percent=100, done=True)
    except Exception as e:  # surface the failure to the UI
        _progress.update(active=False, phase="error", error=str(e))


def _content_length(url):
    """Best-effort total download size (bytes) via a HEAD request."""
    try:
        r = subprocess.run(["curl", "-sIL", "--connect-timeout", "15", url],
                           capture_output=True, text=True, timeout=40)
        size = 0
        for line in r.stdout.splitlines():
            if line.lower().startswith("content-length:"):
                try:
                    size = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
        return size
    except Exception:
        return 0

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
    _progress.update(active=True, phase="downloading", percent=0, error="", done=False)

    # Use curl rather than urllib: urllib can stall indefinitely on GitHub's
    # release-asset CDN redirect. curl resumes (-C -), retries, and aborts a
    # stalled transfer (--speed-time/--speed-limit) so it never hangs forever.
    total = _content_length(download_url)
    proc = subprocess.Popen(
        ["curl", "-fL", "-o", dmg, download_url,
         "-C", "-",
         "--retry", "10", "--retry-delay", "3", "--retry-all-errors",
         "--connect-timeout", "20",
         "--speed-time", "30", "--speed-limit", "1024",
         "--max-time", str(timeout)],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    # Poll the partial file size to report download percentage to the UI.
    while proc.poll() is None:
        if total and os.path.exists(dmg):
            _progress["percent"] = min(99, int(os.path.getsize(dmg) * 100 / total))
        time.sleep(0.4)
    err = proc.stderr.read() if proc.stderr else ""
    if proc.returncode != 0 or not os.path.exists(dmg) or os.path.getsize(dmg) < 100000:
        detail = err.strip().splitlines()[-1] if err.strip() else "incomplete download"
        raise RuntimeError("Download failed — " + detail)
    _progress.update(percent=100, phase="installing")

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
    q_new = shlex.quote(new_app)
    q_tgt = shlex.quote(target)
    q_tgtnew = shlex.quote(target + ".new")
    q_mount = shlex.quote(mountpoint)
    q_dmg = shlex.quote(dmg)
    helper = os.path.join(tmpdir, "install.sh")
    script = f"""#!/bin/bash
sleep 1
# Quit the running app; wait until it has fully exited, then force-kill if needed.
pkill -f 'Finland Schedule.app/Contents/MacOS' 2>/dev/null
for i in $(seq 1 30); do pgrep -f 'Finland Schedule.app/Contents/MacOS' >/dev/null || break; sleep 0.5; done
pkill -9 -f 'Finland Schedule.app/Contents/MacOS' 2>/dev/null
sleep 1
# Swap in the new app bundle (staged copy first, so a failure can't delete the app).
if ditto {q_new} {q_tgtnew} ; then
  rm -rf {q_tgt}
  mv {q_tgtnew} {q_tgt}
  xattr -dr com.apple.quarantine {q_tgt} 2>/dev/null
fi
hdiutil detach {q_mount} -force 2>/dev/null
rm -f {q_dmg} 2>/dev/null
# Wait for the server port to be released before relaunching, then retry once.
for i in $(seq 1 40); do lsof -nP -iTCP:5050 -sTCP:LISTEN >/dev/null 2>&1 || break; sleep 0.5; done
open {q_tgt} || (sleep 3; open {q_tgt})
"""
    with open(helper, "w") as f:
        f.write(script)
    os.chmod(helper, 0o755)
    subprocess.Popen(["/bin/bash", helper], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return target
