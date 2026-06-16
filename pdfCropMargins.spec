# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app_launcher.py'],
    pathex=['/Users/206870216/Downloads/5. Python/pdfCropMargins/src'],
    binaries=[
        ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/pymupdf/_mupdf.so', 'pymupdf'),
        ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/pymupdf/libmupdfcpp.so', 'pymupdf'),
        ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/pymupdf/libmupdf.dylib', 'pymupdf'),
    ],
    datas=[
        ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/pymupdf', 'pymupdf'),
        ('/Library/Frameworks/Python.framework/Versions/3.13/lib/python3.13/site-packages/fitz', 'fitz'),
    ],
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
        'fitz',
        'pymupdf',
        'pymupdf.mupdf',
        'pymupdf.pymupdf',
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
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
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
app = BUNDLE(
    coll,
    name='pdfCropMargins.app',
    icon=None,
    bundle_identifier=None,
)
