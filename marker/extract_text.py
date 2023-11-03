import os

from marker.ocr.segment import ocr_bbox
from marker.ocr.page import ocr_entire_page_ocrmp
from marker.ocr.utils import detect_bad_ocr, font_flags_decomposer
from marker.settings import settings
from marker.schema import Span, Line, Block, Page

os.environ["TESSDATA_PREFIX"] = settings.TESSDATA_PREFIX


def get_single_page_blocks(doc, pnum: int, tess_lang: str, spell_lang=None, ocr=False):
    page = doc[pnum]
    if ocr:
        blocks = ocr_entire_page_ocrmp(page, tess_lang, spell_lang)
    else:
        blocks = page.get_text("dict", sort=True, flags=settings.TEXT_FLAGS)["blocks"]

    ocr_segments = 0
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
                    ocr_segments += 1
                    block_text = ocr_bbox(page, block_text, bbox, tess_lang)
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
    return page_blocks, ocr_segments


def get_text_blocks(doc, tess_lang: str, spell_lang: str, max_pages: int | None=None):
    all_blocks = []
    toc = doc.get_toc()
    page_extracted = False
    ocr_segments = 0
    ocr_pages = 0
    for pnum, page in enumerate(doc):
        if max_pages and pnum >= max_pages:
            break
        blocks, ocr_seg = get_single_page_blocks(doc, pnum, tess_lang)
        ocr_segments += ocr_seg
        page_obj = Page(blocks=blocks, pnum=pnum)

        # OCR page if we got minimal text, or if we got too many spaces
        conditions = [
            (
                    (len(page_obj.get_nonblank_lines()) < 3 and not page_extracted)  # Possibly PDF has no text, and needs full OCR
                    or (len(page_obj.prelim_text) > 0 and detect_bad_ocr(page_obj.prelim_text, spell_lang)) # Bad OCR
            ),
            1 < pnum < len(doc) - 1
        ]
        if all(conditions) or settings.OCR_ALL_PAGES:
            blocks = get_single_page_blocks(doc, pnum, tess_lang, spell_lang, ocr=True)
            page_obj = Page(blocks=blocks, pnum=pnum)
            page_extracted = False
            ocr_pages += 1
        else:
            page_extracted = True

        all_blocks.append(page_obj)
    return all_blocks, toc, {"ocr_segments": ocr_segments, "ocr_pages": ocr_pages}
