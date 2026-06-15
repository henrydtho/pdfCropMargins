Building pdfCropMargins for Windows
=====================================

Prerequisites (run these on a Windows machine):

  1. Install Python 3.11+ from https://python.org  (check "Add to PATH")
  2. Open a Command Prompt in this folder and run:

       pip install pyinstaller pymupdf pdfCropMargins

  3. Confirm the pdfCropMargins package installed into the Python site-packages
     AND that the src/ folder is present here (it contains the source package).

Build steps:

  pyinstaller pdfCropMargins_windows.spec

Output:

  dist\pdfCropMargins\pdfCropMargins.exe   — the main executable
  dist\pdfCropMargins\                     — the full distribution folder

  Copy or zip the entire dist\pdfCropMargins\ folder to distribute the app.
  The .exe is NOT standalone — it requires the other files in that folder.

  To make a single-file .exe instead, change the spec:
    - Remove the coll = COLLECT(...) section entirely
    - In EXE(...), change the 3rd argument from [] to a.binaries + a.datas
    - Add onefile=True  (or use the --onefile flag on the command line)

Optional — add a custom icon:
  Replace  icon=None  in pdfCropMargins_windows.spec with:
    icon='path\\to\\icon.ico'

Notes:
  - The Windows version uses tkinter dialogs instead of macOS osascript.
  - Double-clicking the .exe shows the mode dialog (Single PDF / Batch Folder).
  - CLI usage is identical to the macOS version:
      pdfCropMargins.exe [options] input.pdf
