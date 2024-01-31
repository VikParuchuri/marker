import io
from typing import List, Optional

import fitz as pymupdf
import ocrmypdf
from spellchecker import SpellChecker

from marker.ocr.utils import detect_bad_ocr
from marker.schema import Block

from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


ocrmypdf.configure_logging(verbosity=ocrmypdf.Verbosity.quiet)


def ocr_entire_page(
    page, lang: str, user_settings, pnum, spellchecker: Optional[SpellChecker] = None
) -> List[Block]:
    global settings
    settings = user_settings

    if settings.OCR_ENGINE == "tesseract":
        logger.info("going to use tesseract")
        return ocr_entire_page_tess(page, lang, pnum, spellchecker)
    elif settings.OCR_ENGINE == "ocrmypdf":
        logger.info("going to use ocrmypdf")
        return ocr_entire_page_ocrmp(page, lang, pnum, spellchecker)
    else:
        raise ValueError(f"Unknown OCR engine {settings.OCR_ENGINE}")


def ocr_entire_page_tess(
    page, lang: str, pnum, spellchecker: Optional[SpellChecker] = None
) -> List[Block]:
    try:
        full_tp = page.get_textpage_ocr(
            flags=settings.TEXT_FLAGS, dpi=settings.OCR_DPI, full=True, language=lang
        )
        blocks = page.get_text(
            "dict", sort=True, flags=settings.TEXT_FLAGS, textpage=full_tp
        )["blocks"]
        full_text = page.get_text(
            "text", sort=True, flags=settings.TEXT_FLAGS, textpage=full_tp
        )

        if len(full_text) == 0:
            return []

        logger.info(f"ocr completed for page number {pnum}")

        # Check if OCR worked. If it didn't, return empty list
        # OCR can fail if there is a scanned blank page with some faint text impressions, for example
        if detect_bad_ocr(full_text, spellchecker):
            return []
    except RuntimeError:
        return []
    return blocks


def ocr_entire_page_ocrmp(
    page, lang: str, pnum, spellchecker: Optional[SpellChecker] = None
) -> List[Block]:
    # Use ocrmypdf to get OCR text for the whole page
    src = page.parent  # the page's document
    blank_doc = pymupdf.open()  # make temporary 1-pager
    blank_doc.insert_pdf(
        src, from_page=page.number, to_page=page.number, annots=False, links=False
    )
    pdfbytes = blank_doc.tobytes()
    inbytes = io.BytesIO(pdfbytes)  # transform to BytesIO object
    outbytes = io.BytesIO()  # let ocrmypdf store its result pdf here
    ocrmypdf.ocr(
        inbytes,
        outbytes,
        language=lang,
        output_type="pdf",
        redo_ocr=None if settings.OCR_ALL_PAGES else True,
        force_ocr=True if settings.OCR_ALL_PAGES else None,
        progress_bar=False,
        optimize=False,
        fast_web_view=1e6,
        skip_big=15,  # skip images larger than 15 megapixels
        tesseract_timeout=settings.TESSERACT_TIMEOUT,
        tesseract_non_ocr_timeout=settings.TESSERACT_TIMEOUT,
    )
    logger.info(f"completed ocr for page number {pnum}")
    ocr_pdf = pymupdf.open("pdf", outbytes.getvalue())  # read output as fitz PDF
    blocks = ocr_pdf[0].get_text("dict", sort=True, flags=settings.TEXT_FLAGS)["blocks"]
    full_text = ocr_pdf[0].get_text("text", sort=True, flags=settings.TEXT_FLAGS)

    # Make sure the original pdf/epub/mobi bbox and the ocr pdf bbox are the same
    assert page.bound() == ocr_pdf[0].bound()

    if len(full_text) == 0:
        return []

    if detect_bad_ocr(full_text, spellchecker):
        return []

    return blocks
