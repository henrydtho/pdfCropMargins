"""PyInstaller entry point for pdfCropMargins.app

This file must have a different name than 'pdfCropMargins.py' to avoid
shadowing the pdfCropMargins package at import time.

When launched as a double-clicked .app with no arguments, this shows a native
macOS dialog to pick a single PDF or a folder for batch processing, then crops
all selected PDFs with automatic whitespace detection (no manual crop settings
needed).  When called with CLI arguments, it delegates straight to the normal
pdfCropMargins main() so all existing flags still work.
"""

import sys
import os
import subprocess


# ---------------------------------------------------------------------------
# Native macOS dialog helpers (all via osascript so no tkinter needed)
# ---------------------------------------------------------------------------

def _ask_mode():
    """Show a dialog asking for single-file or batch-folder mode.
    Returns 'single', 'batch', or None if the user cancels."""
    script = (
        'set btn to button returned of '
        '(display dialog "How would you like to crop?" '
        'buttons {"Cancel", "Batch Folder", "Single PDF"} '
        'default button "Single PDF" '
        'with title "pdfCropMargins")\n'
        'return btn'
    )
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True)
        btn = r.stdout.strip()
        if btn == "Single PDF":
            return "single"
        if btn == "Batch Folder":
            return "batch"
        return None
    except Exception:
        return None


def _pick_file():
    """Show a native file picker for a single PDF. Returns path or None."""
    script = (
        'POSIX path of '
        '(choose file with prompt "Select a PDF file:" '
        'of type {"com.adobe.pdf", "pdf"})'
    )
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True)
        path = r.stdout.strip()
        return path or None
    except Exception:
        return None


def _pick_folder():
    """Show a native folder picker. Returns path (no trailing slash) or None."""
    script = (
        'POSIX path of '
        '(choose folder with prompt "Select folder containing PDF files:")'
    )
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True)
        path = r.stdout.strip().rstrip("/")
        return path or None
    except Exception:
        return None


def _notify(title, message):
    """Show a macOS notification banner."""
    safe_msg = message.replace('"', '\\"')
    safe_title = title.replace('"', '\\"')
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True)
    except Exception:
        pass


def _alert(title, message):
    """Show a blocking alert dialog (used for errors)."""
    safe_msg = message.replace('"', '\\"').replace("\\n", " ")[:400]
    safe_title = title.replace('"', '\\"')
    script = (
        f'display alert "{safe_title}" '
        f'message "{safe_msg}" '
        'buttons {"OK"} default button "OK"'
    )
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Guided GUI flow (used when the .app is double-clicked with no arguments)
# ---------------------------------------------------------------------------

def _run_gui():
    """Show mode dialog, pick file(s), and crop with automatic settings."""
    try:
        from pdfCropMargins.pdfCropMargins import crop
    except Exception as e:
        _alert("pdfCropMargins — Import Error", str(e))
        sys.exit(1)

    mode = _ask_mode()
    if mode is None:
        sys.exit(0)

    if mode == "single":
        path = _pick_file()
        if not path:
            sys.exit(0)
        pdfs = [path]

    else:  # batch
        folder = _pick_folder()
        if not folder:
            sys.exit(0)
        try:
            pdfs = sorted(
                os.path.join(folder, f)
                for f in os.listdir(folder)
                if f.lower().endswith(".pdf")
            )
        except Exception as e:
            _alert("pdfCropMargins — Folder Error", str(e))
            sys.exit(1)
        if not pdfs:
            _alert("pdfCropMargins", "No PDF files found in the selected folder.")
            sys.exit(0)

    if mode == "single":
        _notify("pdfCropMargins", f"Processing {os.path.basename(pdfs[0])}…")
    else:
        _notify("pdfCropMargins", f"Processing {len(pdfs)} PDF(s) in batch…")

    ok = 0
    errors = []
    for pdf_path in pdfs:
        try:
            # Auto-crop with PyMuPDF rendering (-c m) so no external tools are
            # needed.  -dlp removes trailing pages that are only a page number
            # or date.  Save output to the same folder as the input.
            output_dir = os.path.dirname(os.path.abspath(pdf_path))
            output_path, exit_code, stdout_str, stderr_str = crop(
                [pdf_path, "-c", "m", "-dlp", "-a4", "0", "-25", "0", "0", "-o", output_dir], string_io=True
            )
            if exit_code in (0, None):
                ok += 1
            else:
                errors.append(os.path.basename(pdf_path))
                if len(errors) == 1:
                    # Show the error output for the first failure to help diagnose.
                    detail = (stderr_str or stdout_str or "unknown error").strip()
                    _alert(
                        f"pdfCropMargins — Error on {os.path.basename(pdf_path)}",
                        detail[:400],
                    )
        except Exception as e:
            import traceback
            errors.append(os.path.basename(pdf_path))
            _alert(
                f"pdfCropMargins — Exception on {os.path.basename(pdf_path)}",
                traceback.format_exc()[:400],
            )

    if mode == "single":
        if errors:
            _notify("pdfCropMargins", f"Error cropping {errors[0]}")
        else:
            _notify("pdfCropMargins", f"Done — {os.path.basename(pdfs[0])}")
    else:
        msg = f"Cropped {ok} of {len(pdfs)} PDF(s)"
        if errors:
            msg += f" — {len(errors)} error(s)"
        _notify("pdfCropMargins", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    from pdfCropMargins.pdfCropMargins import main as _pdfcm_main
    _pdfcm_main()


if getattr(sys, "frozen", False) and len(sys.argv) == 1:
    # Launched as a double-clicked .app — use the guided GUI flow.
    _run_gui()
else:
    # Called with CLI arguments (or in development) — normal behaviour.
    main()

