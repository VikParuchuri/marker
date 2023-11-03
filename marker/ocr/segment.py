import fitz as pymupdf

from marker.settings import settings


def ocr_bbox(page, old_text, bbox, lang: str):
    pix = page.get_pixmap(dpi=settings.SEGMENT_DPI, clip=bbox)

    try:
        ocrpdf = pymupdf.open("pdf", pix.pdfocr_tobytes(language=lang))
        ocrpage = ocrpdf[0]
        new_text = ocrpage.get_text()  # extract OCR-ed text
    except RuntimeError:
        # If the OCR fails, just return the original text
        return old_text

    if not new_text.strip():
        # If the OCR data is blank, return old text
        return old_text

    # Tesseract ignores leading spaces, hence some corrections
    lblanks = len(old_text) - len(old_text.lstrip())
    rblanks = len(old_text) - len(old_text.rstrip())

    # prefix/suffix OCRed text with this many spaces
    new_text = " " * lblanks + new_text + " " * rblanks
    return new_text
