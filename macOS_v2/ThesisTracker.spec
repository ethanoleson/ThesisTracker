# ThesisTracker.spec

block_cipher = None

a = Analysis(
    ['ThesisTrackerv1.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ThesisTracker',
    console=False,
    icon='MyApp.icns',
)

app = BUNDLE(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='ThesisTracker.app',
    icon='MyApp.icns',
    bundle_identifier='com.yourname.thesistracker',
)