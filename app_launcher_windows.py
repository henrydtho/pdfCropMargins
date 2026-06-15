"""PyInstaller entry point for pdfCropMargins on Windows.

This file must have a different name than 'pdfCropMargins.py' to avoid
shadowing the pdfCropMargins package at import time.

When launched as a double-clicked .exe with no arguments, this shows native
Windows dialogs to pick a single PDF or a folder for batch processing, then
crops all selected PDFs with automatic whitespace detection (no manual crop
settings needed).  When called with CLI arguments, it delegates straight to the
normal pdfCropMargins main() so all existing flags still work.
"""

import sys
import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox


# ---------------------------------------------------------------------------
# Windows dialog helpers (using tkinter — included with Python on Windows)
# ---------------------------------------------------------------------------

def _make_root():
    """Create a hidden root window and bring it to the foreground."""
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    return root


def _ask_mode():
    """Show a dialog asking for single-file or batch-folder mode.
    Returns 'single', 'batch', or None if the user cancels."""
    root = _make_root()
    result = [None]

    dialog = tk.Toplevel(root)
    dialog.title("pdfCropMargins")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)

    tk.Label(
        dialog,
        text="How would you like to crop?",
        font=("Segoe UI", 11),
        padx=24,
        pady=18,
    ).pack()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(padx=24, pady=(0, 18))

    def choose_single():
        result[0] = "single"
        dialog.destroy()

    def choose_batch():
        result[0] = "batch"
        dialog.destroy()

    def cancel():
        result[0] = None
        dialog.destroy()

    tk.Button(btn_frame, text="Single PDF",   command=choose_single, width=13).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Batch Folder", command=choose_batch,  width=13).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="Cancel",       command=cancel,        width=9).pack(side=tk.LEFT, padx=5)

    dialog.protocol("WM_DELETE_WINDOW", cancel)
    dialog.grab_set()
    root.wait_window(dialog)
    root.destroy()
    return result[0]


def _pick_file():
    """Show a native file picker for a single PDF. Returns path or None."""
    root = _make_root()
    path = filedialog.askopenfilename(
        title="Select a PDF file",
        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        parent=root,
    )
    root.destroy()
    return path or None


def _pick_folder():
    """Show a native folder picker. Returns path (no trailing slash) or None."""
    root = _make_root()
    folder = filedialog.askdirectory(
        title="Select folder containing PDF files",
        parent=root,
    )
    root.destroy()
    return folder.rstrip("/\\") if folder else None


def _notify(title, message):
    """Show a non-blocking info dialog (used for start/done status)."""
    root = _make_root()
    messagebox.showinfo(title, message, parent=root)
    root.destroy()


def _alert(title, message):
    """Show a blocking error dialog."""
    root = _make_root()
    messagebox.showerror(title, message[:500], parent=root)
    root.destroy()


# ---------------------------------------------------------------------------
# Smart PDF cropper using PyMuPDF directly
# ---------------------------------------------------------------------------

# Matches the browser-generated print footer: date on the left, page number on
# the right.  These span the full page width and must be excluded from the
# content bounding box.
_DATE_RE = re.compile(
    r"^\d{1,2}/\d{1,2}/\d{2,4}",  # starts with a date like 5/13/26
)
_PAGE_NUM_RE = re.compile(
    r"^\s*(?:page\s+\d+|\d+\s+of\s+\d+|-?\s*\d+\s*-?|page\s+\d+\s+of\s+\d+)\s*$",
    re.IGNORECASE,
)


def _is_browser_footer_block(block, page_width, page_height):
    """Return True if this text block looks like a browser print footer/header."""
    bx0, by0, bx1, by1 = block[0], block[1], block[2], block[3]
    text = block[4].strip()

    is_full_width = bx0 < 5 and bx1 > page_width - 5
    if not is_full_width:
        return False

    in_header = by1 < page_height * 0.02
    in_footer = by0 > page_height * 0.98
    if not (in_header or in_footer):
        return False

    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if _DATE_RE.match(line) or _PAGE_NUM_RE.match(line):
            return True

    return False


def smart_crop_pdf(input_path, output_path, margin_pt=5):
    """Crop each page of *input_path* to the bounding box of its actual content
    and save to *output_path*.

    Returns a tuple (pages_cropped, total_pages).
    """
    import fitz  # PyMuPDF

    doc = fitz.open(input_path)
    pages_cropped = 0

    for page in doc:
        try:
            pw = page.rect.width
            ph = page.rect.height

            rects = []

            for block in page.get_text("blocks"):
                if not block[4].strip():
                    continue
                if _is_browser_footer_block(block, pw, ph):
                    continue
                rects.append(fitz.Rect(block[0], block[1], block[2], block[3]))

            if not rects:
                continue

            bbox = rects[0]
            for r in rects[1:]:
                bbox = bbox | r

            new_crop = fitz.Rect(
                0,
                max(0,  bbox.y0 - margin_pt),
                pw,
                min(ph, bbox.y1 + 50),
            )

            current_crop = page.cropbox
            area_reduction = (
                (current_crop.width * current_crop.height)
                - (new_crop.width * new_crop.height)
            )
            if area_reduction > 1:
                page.set_cropbox(new_crop)
                pages_cropped += 1

        except Exception:
            continue

    total_pages = doc.page_count
    doc.save(output_path)
    doc.close()
    return pages_cropped, total_pages


# ---------------------------------------------------------------------------
# Guided GUI flow (used when the .exe is double-clicked with no arguments)
# ---------------------------------------------------------------------------

def _run_gui():
    """Show mode dialog, pick file(s), and crop with automatic settings."""
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

    ok = 0
    errors = []
    for pdf_path in pdfs:
        try:
            base, ext = os.path.splitext(pdf_path)
            output_path = base + "_cropped" + ext
            smart_crop_pdf(pdf_path, output_path)
            ok += 1
        except Exception:
            import traceback
            errors.append(os.path.basename(pdf_path))
            if len(errors) == 1:
                _alert(
                    f"pdfCropMargins \u2014 Error on {os.path.basename(pdf_path)}",
                    traceback.format_exc()[:400],
                )

    if mode == "single":
        if errors:
            _notify("pdfCropMargins", f"Error cropping {errors[0]}")
        else:
            _notify("pdfCropMargins", f"Done \u2014 cropped {os.path.basename(pdfs[0])}")
    else:
        msg = f"Cropped {ok} of {len(pdfs)} PDF(s) successfully."
        if errors:
            msg += f"\n{len(errors)} file(s) had errors."
        _notify("pdfCropMargins", msg)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    from pdfCropMargins.pdfCropMargins import main as _pdfcm_main
    _pdfcm_main()


if getattr(sys, "frozen", False) and len(sys.argv) == 1:
    # Launched as a double-clicked .exe — use the guided GUI flow.
    _run_gui()
else:
    main()
