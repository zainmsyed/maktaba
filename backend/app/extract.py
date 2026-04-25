from __future__ import annotations

import io
from pathlib import Path
from typing import Iterable, Tuple


def extract_text_and_fallback(pdf_path: Path | str, *, text_threshold: int = 50, ocr_dpi: int = 200) -> Iterable[Tuple[int, str, bool]]:
    """
    Extract per-page text from a PDF using PyMuPDF (fitz). If a page's extracted
    text is shorter than ``text_threshold``, optionally run OCR (pytesseract)
    on a rasterized image of the page and return the OCR text instead.

    Yields tuples of (page_number (1-based), extracted_text, ocr_used).

    Note: Both PyMuPDF (``fitz``) and Pillow / pytesseract are optional at
    import-time. If pytesseract or Pillow are not available the function will
    return the best text it can extract from the PDF text layer and mark
    ``ocr_used`` as False for pages that would otherwise need OCR.
    """
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "PyMuPDF is required for PDF text extraction. Install with `pip install PyMuPDF`.") from exc

    # Optional OCR dependencies
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        _ocr_available = True
    except Exception:
        pytesseract = None  # type: ignore
        Image = None  # type: ignore
        _ocr_available = False

    doc = fitz.open(str(pdf_path))
    page_count = doc.page_count

    for idx in range(page_count):
        page_number = idx + 1
        page = doc.load_page(idx)
        text = page.get_text("text") or ""
        cleaned = text.strip()

        if len(cleaned) >= text_threshold:
            yield page_number, cleaned, False
            continue

        # Page looks like it might be scanned — attempt OCR if available
        if not _ocr_available:
            # OCR not available: return whatever short text we got and mark ocr_used False
            yield page_number, cleaned, False
            continue

        # Rasterize the page at a higher scale for OCR
        mat = fitz.Matrix(ocr_dpi / 72, ocr_dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(png_bytes))

        try:
            ocr_text = pytesseract.image_to_string(img) or ""
        except Exception:
            ocr_text = ""

        ocr_clean = ocr_text.strip()
        if len(ocr_clean) >= text_threshold:
            yield page_number, ocr_clean, True
        else:
            # OCR did not yield useful text; return the short extracted text if any
            yield page_number, (ocr_clean or cleaned), bool(ocr_clean)

    doc.close()
