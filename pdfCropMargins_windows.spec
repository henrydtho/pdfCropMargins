# -*- mode: python ; coding: utf-8 -*-
# Windows PyInstaller spec for pdfCropMargins
# Build with: pyinstaller pdfCropMargins_windows.spec

a = Analysis(
    ['app_launcher_windows.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'pdfCropMargins',
        'pdfCropMargins.pdfCropMargins',
        'pdfCropMargins.main_pdfCropMargins',
        'pdfCropMargins.external_program_calls',
        'pdfCropMargins.calculate_bounding_boxes',
        'pdfCropMargins.pymupdf_routines',
        'pdfCropMargins.manpage_data',
        'pdfCropMargins.prettified_argparse',
        'pdfCropMargins.gui',
        'pdfCropMargins.directory_locator',
        'pdfCropMargins.get_window_sizing_info',
        'pdfCropMargins.vendor',
        'pdfCropMargins.vendor.pysimplegui_4_foss',
        'tkinter',
        'tkinter.filedialog',
        'tkinter.messagebox',
    ],
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
    [],
    exclude_binaries=True,
    name='pdfCropMargins',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # No terminal window — GUI-only app
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # Replace with path to a .ico file if you have one
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='pdfCropMargins',
)
