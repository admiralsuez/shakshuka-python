# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('templates', 'templates'), ('static', 'static'), ('update_manager.py', '.'), ('installer.py', '.')]
binaries = []
hiddenimports = ['flask', 'flask_cors', 'cryptography', 'schedule', 'psutil', 'winreg', 'requests', 'requests.adapters', 'requests.auth', 'requests.cookies', 'requests.exceptions', 'requests.models', 'requests.sessions', 'requests.utils', 'urllib3', 'urllib3.util', 'urllib3.util.retry', 'urllib3.util.connection', 'certifi', 'charset_normalizer']
tmp_ret = collect_all('requests')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='Shakshuka',
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
