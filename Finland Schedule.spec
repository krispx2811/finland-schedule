# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[('schedule_app/templates', 'schedule_app/templates'), ('schedule_app/static', 'schedule_app/static'), ('New Schedule.xlsx', '.')],
    hiddenimports=['schedule_app', 'schedule_app.database', 'schedule_app.models', 'schedule_app.config', 'schedule_app.scheduler', 'schedule_app.excel_import', 'schedule_app.excel_export', 'schedule_app.pdf_export', 'schedule_app.web_app', 'schedule_app.updater', 'certifi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Finland Schedule',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='Finland Schedule.app',
    icon=None,
    bundle_identifier=None,
)
