import fitz as pymupdf
import os
from marker.settings import settings
from marker.schema import Span, Line, Block, Page
import string

os.environ["TESSDATA_PREFIX"] = settings.TESSDATA_PREFIX
TEXT_FLAGS = ~pymupdf.TEXT_PRESERVE_LIGATURES & pymupdf.TEXT_PRESERVE_WHITESPACE & ~pymupdf.TEXT_PRESERVE_IMAGES & ~pymupdf.TEXT_INHIBIT_SPACES & pymupdf.TEXT_DEHYPHENATE & pymupdf.TEXT_MEDIABOX_CLIP


def ocr_entire_page(page, lang: str):
    try:
        full_tp = page.get_textpage_ocr(flags=TEXT_FLAGS, dpi=settings.DPI, full=True, language=lang)
        blocks = page.get_text("dict", sort=True, flags=TEXT_FLAGS, textpage=full_tp)["blocks"]
    except RuntimeError:
        return []
    return blocks


def ocr_bbox(page, old_text, bbox, lang: str):
    pix = page.get_pixmap(dpi=settings.DPI, clip=bbox)

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

    # prefix OCRed text with this many spaces
    new_text = " " * lblanks + new_text
    return new_text


def font_flags_decomposer(flags):
    """Make font flags human readable."""
    l = []
    if flags & 2 ** 0:
        l.append("superscript")
    if flags & 2 ** 1:
        l.append("italic")
    if flags & 2 ** 2:
        l.append("serifed")
    else:
        l.append("sans")
    if flags & 2 ** 3:
        l.append("monospaced")
    else:
        l.append("proportional")
    if flags & 2 ** 4:
        l.append("bold")
    return "_".join(l)


def get_single_page_blocks(page, pnum: int, lang: str, ocr=False):
    if ocr:
        blocks = ocr_entire_page(page, lang)
    else:
        blocks = page.get_text("dict", sort=True, flags=TEXT_FLAGS)["blocks"]

    page_blocks = []
    span_id = 0
    for block_idx, block in enumerate(blocks):
        block_lines = []
        for l in block["lines"]:
            spans = []
            for i, s in enumerate(l["spans"]):
                block_text = s["text"]
                bbox = s["bbox"]
                # Find if any of the elements in invalid chars are in block_text
                if set(settings.INVALID_CHARS).intersection(block_text):  # invalid characters encountered!
                    # invoke OCR
                    block_text = ocr_bbox(page, block_text, bbox, lang)
                # print("block %i, bbox: %s, text: %s" % (block_idx, bbox, block_text))
                span_obj = Span(
                    text=block_text,
                    bbox=bbox,
                    span_id=f"{pnum}_{span_id}",
                    font=f"{s['font']}_{font_flags_decomposer(s['flags'])}", # Add font flags to end of font
                    color=s["color"],
                    ascender=s["ascender"],
                    descender=s["descender"],
                )
                spans.append(span_obj)  # Text, bounding box, span id
                span_id += 1
            line_obj = Line(
                spans=spans,
                bbox=l["bbox"]
            )
            # Only select valid lines, with positive bboxes
            if line_obj.area > 0:
                block_lines.append(line_obj)
        block_obj = Block(
            lines=block_lines,
            bbox=block["bbox"],
            pnum=pnum
        )
        # Only select blocks with multiple lines
        if len(block_lines) > 0:
            page_blocks.append(block_obj)
    return page_blocks


def alphanum_ratio(text):
    alphanumeric_count = sum([1 for c in text if c.isalnum()])

    if alphanumeric_count == 0:
        return 0

    ratio = alphanumeric_count / len(text)
    return ratio


def get_text_blocks(doc, lang, max_pages=None):
    all_blocks = []
    toc = doc.get_toc()
    for pnum, page in enumerate(doc):
        if max_pages and pnum >= max_pages:
            break
        blocks = get_single_page_blocks(page, pnum, lang)
        page_obj = Page(blocks=blocks, pnum=pnum)

        # OCR page if we got minimal text, or if we got too many spaces
        conditions = [
            len(page_obj.get_nonblank_lines()) < 3,
            (
                    alphanum_ratio(page_obj.prelim_text) < .7 # Garbled or bad OCR text
                    or (page_obj.prelim_text.count(" ") / len(page_obj.prelim_text)) > .3 ## too many spaces on the page
            ),
            2 < pnum < len(doc) - 2
        ]
        if all(conditions):
            blocks = get_single_page_blocks(page, pnum, lang, ocr=True)
            page_obj = Page(blocks=blocks, pnum=pnum)
        all_blocks.append(page_obj)

    return all_blocks, toc
