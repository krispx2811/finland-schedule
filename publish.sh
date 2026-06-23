#!/bin/bash
#
# Publish a new version of Finland Schedule to everyone.
#
#   ./publish.sh <version> ["release notes"]
#   ./publish.sh 1.0.1 "Fixed the schedule generator"
#
# It bumps the version, builds the .dmg, creates a GitHub Release, and updates
# version.json. After this runs, every user's app shows the update on next launch.
#
set -euo pipefail
cd "$(dirname "$0")"

VERSION="${1:-}"
NOTES="${2:-New version ${VERSION}}"
REPO="krispx2811/finland-schedule"
APP="Finland Schedule"
ASSET="Finland-Schedule.dmg"

if [ -z "$VERSION" ]; then
    echo "Usage: ./publish.sh <version> [\"release notes\"]"
    echo "Example: ./publish.sh 1.0.1 \"Fixed the schedule generator\""
    exit 1
fi

echo "==> 1/5 Setting version to $VERSION"
python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1]
p = "schedule_app/config.py"
s = open(p).read()
s = re.sub(r'APP_VERSION\s*=\s*".*"', f'APP_VERSION = "{v}"', s, count=1)
open(p, "w").write(s)
PY
git add schedule_app/config.py
git commit -q -m "Release $VERSION" || true

echo "==> 2/5 Building the app"
rm -rf build "dist/$APP.app" "dist/$APP" "dist/data"
python3 -m PyInstaller --noconfirm "$APP.spec" >/dev/null
codesign --force --deep -s - "dist/$APP.app" >/dev/null 2>&1 || true

echo "==> 3/5 Packaging the .dmg"
STAGE="$(mktemp -d)"
cp -R "dist/$APP.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
rm -f "dist/$APP.dmg" "dist/$ASSET"
hdiutil create -volname "$APP" -srcfolder "$STAGE" -fs HFS+ -format UDZO -ov "dist/$APP.dmg" >/dev/null
rm -rf "$STAGE"
cp "dist/$APP.dmg" "dist/$ASSET"

echo "==> 4/5 Creating GitHub release v$VERSION"
gh release create "v$VERSION" "dist/$ASSET" --repo "$REPO" --title "$APP $VERSION" --notes "$NOTES"

echo "==> 5/5 Updating version.json (what users' apps check)"
python3 - "$VERSION" "$NOTES" <<'PY'
import json, sys
v, notes = sys.argv[1], sys.argv[2]
data = {
    "version": v,
    "notes": notes,
    "download_url": "https://github.com/krispx2811/finland-schedule/releases/latest/download/Finland-Schedule.dmg",
}
open("version.json", "w").write(json.dumps(data, indent=2) + "\n")
PY
git add version.json
git commit -q -m "Publish $VERSION"
git push -q origin main

echo ""
echo "✅ Published $VERSION. Everyone's app will offer the update within a few minutes of next launch."
