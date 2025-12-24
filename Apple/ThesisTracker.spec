# ThesisTracker.spec

block_cipher = None

a = Analysis(
    ['ThesisTrackerv1.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ThesisTracker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # IMPORTANT: GUI app
    disable_windowed_traceback=False,
)

app = BUNDLE(
    exe,
    a.binaries,
    a.datas,
    name='ThesisTracker.app',
    icon='MyApp.icns',   # add .icns later if you want
    bundle_identifier='edu.yourname.ThesisTracker',
)
