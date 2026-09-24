# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：三角洲密码工具（onedir，无需 Python 环境）。"""

from PyInstaller.utils.hooks import collect_all

# rapidocr_onnxruntime：收集全部子模块 + config.yaml（离线 OCR 引擎）
rapid_datas, rapid_binaries, rapid_hidden = collect_all('rapidocr_onnxruntime')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=rapid_binaries,
    datas=rapid_datas,
    hiddenimports=rapid_hidden + [
        'onnxruntime',
        'pystray',
        'PIL._tkinter_finder',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib', 'scipy', 'pytest', 'PyQt5', 'PySide6', 'IPython',
        'pandas', 'tkinter.test',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='三角洲密码工具',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='三角洲密码工具',
)
