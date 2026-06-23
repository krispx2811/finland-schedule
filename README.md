# Finland Schedule

A staff scheduling app for Mac (Flask + PyInstaller, packaged as a `.dmg`).

## Download

Get the latest version from the [Releases page](https://github.com/krispx2811/finland-schedule/releases/latest).
Open the `.dmg` and drag **Finland Schedule** into your Applications folder.

## Auto-update

The app checks [`version.json`](version.json) on launch. When a newer version is
published here, every user's app shows an "update available" banner and can
download + install it. User data is stored locally on each Mac
(`~/Library/Application Support/Finland Schedule/`) and is never uploaded.

## Publishing a new version (for the maintainer)

Run the publish script with the new version number:

```bash
./publish.sh 1.0.1 "What changed in this release"
```

It bumps the version, builds the DMG, creates a GitHub Release, and updates
`version.json` — after which every user's app will offer the update.

## Build manually

```bash
python3 -m pip install -r requirements.txt
python3 -m PyInstaller --noconfirm "Finland Schedule.spec"
```
