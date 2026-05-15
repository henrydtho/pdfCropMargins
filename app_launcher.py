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
import re
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
    # Escape double-quotes so osascript doesn't choke on them.
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
    """Return True if this text block looks like a browser print footer/header.

    Chrome/headless export adds a line at the very bottom with the print date
    on the left and 'Page N' on the right.  The block spans nearly the full
    page width and sits in the last ~2% of the page height.
    """
    bx0, by0, bx1, by1 = block[0], block[1], block[2], block[3]
    text = block[4].strip()

    # Must span nearly full width (within 5pt of each edge)
    is_full_width = bx0 < 5 and bx1 > page_width - 5
    if not is_full_width:
        return False

    # Must be in the top 2% or bottom 2% of the page
    in_header = by1 < page_height * 0.02
    in_footer = by0 > page_height * 0.98
    if not (in_header or in_footer):
        return False

    # Content must look like a date and/or page number
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for line in lines:
        if _DATE_RE.match(line) or _PAGE_NUM_RE.match(line):
            return True

    return False


def smart_crop_pdf(input_path, output_path, margin_pt=5):
    """Crop each page of *input_path* to the bounding box of its actual content
    and save to *output_path*.

    Steps per page:
      1. Collect bounding boxes from text blocks, vector drawings, and images.
      2. Discard full-width browser print-footer/header blocks (Chrome adds
         these automatically when saving a web page as PDF).
      3. Union the remaining rectangles to find the content bounding box.
      4. Expand by *margin_pt* on each side and set as the page CropBox.

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

            # Use text blocks only for vertical bounds — drawings such as table
            # borders can span nearly the full page height and would prevent the
            # bottom whitespace from being cropped.
            for block in page.get_text("blocks"):
                if not block[4].strip():
                    continue  # skip empty blocks
                if _is_browser_footer_block(block, pw, ph):
                    continue  # skip browser-generated header/footer line
                rects.append(fitz.Rect(block[0], block[1], block[2], block[3]))

            if not rects:
                continue  # nothing to crop on this page

            # Union all content rectangles
            bbox = rects[0]
            for r in rects[1:]:
                bbox = bbox | r

            # Add margin and clamp to page bounds (horizontal kept as full page width)
            new_crop = fitz.Rect(
                0,
                max(0,  bbox.y0 - margin_pt),
                pw,
                min(ph, bbox.y1 + 50),
            )

            # Only apply if it's meaningfully smaller than the current page
            current_crop = page.cropbox
            area_reduction = (
                (current_crop.width * current_crop.height)
                - (new_crop.width * new_crop.height)
            )
            if area_reduction > 1:  # more than 1 sq-pt smaller
                page.set_cropbox(new_crop)
                pages_cropped += 1

        except Exception:
            # If a page has corrupt/unreadable streams, leave it uncropped
            continue

    total_pages = doc.page_count
    doc.save(output_path)
    doc.close()
    return pages_cropped, total_pages


# ---------------------------------------------------------------------------
# Guided GUI flow (used when the .app is double-clicked with no arguments)
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

    if mode == "single":
        _notify("pdfCropMargins", f"Processing {os.path.basename(pdfs[0])}\u2026")
    else:
        _notify("pdfCropMargins", f"Processing {len(pdfs)} PDF(s) in batch\u2026")

    ok = 0
    errors = []
    for pdf_path in pdfs:
        try:
            base, ext = os.path.splitext(pdf_path)
            output_path = base + "_cropped" + ext
            pages_cropped, total = smart_crop_pdf(pdf_path, output_path)
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
            _notify("pdfCropMargins", f"Done \u2014 {os.path.basename(pdfs[0])}")
    else:
        msg = f"Cropped {ok} of {len(pdfs)} PDF(s)"
        if errors:
            msg += f" \u2014 {len(errors)} error(s)"
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
    script = f'display notification "{message}" with title "{title}"'
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True)
    except Exception:
        pass


def _alert(title, message):
    """Show a blocking alert dialog (used for errors)."""
    script = (
        f'display alert "{title}" message "{message}" '
        'buttons {{"OK"}} default button "OK"'
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
                [pdf_path, "-c", "m", "-dlp", "-o", output_dir], string_io=True
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

