import os
from typing import List, Optional, Dict

import pypdfium2 as pdfium
import pypdfium2.internal as pdfium_i

from marker.pdf.filetype import find_filetype
from marker.ocr.utils import font_flags_decomposer
from marker.ocr.heuristics import detect_bad_ocr
from marker.settings import settings
from marker.schema.schema import Span, Line, Block
from marker.schema.page import Page
from pdftext.extraction import dictionary_output

os.environ["TESSDATA_PREFIX"] = settings.TESSDATA_PREFIX


def pdftext_format_to_blocks(page, pnum: int) -> Page:
    page_blocks = []
    span_id = 0
    for block_idx, block in enumerate(page["blocks"]):
        block_lines = []
        for l in block["lines"]:
            spans = []
            for i, s in enumerate(l["spans"]):
                block_text = s["text"].rstrip("\n")
                block_text = block_text.replace("-\n", "") # Remove hyphenated line breaks
                span_obj = Span(
                    text=block_text.rstrip("\n"), # Remove end of line newlines, not spaces
                    bbox=s["bbox"],
                    span_id=f"{pnum}_{span_id}",
                    font=f"{s['font']['name']}_{font_flags_decomposer(s['font']['flags'])}", # Add font flags to end of font
                    font_weight=s["font"]["weight"],
                    font_size=s["font"]["size"],
                )
                spans.append(span_obj)  # Text, bounding box, span id
                span_id += 1
            line_obj = Line(
                spans=spans,
                bbox=l["bbox"],
            )
            # Only select valid lines, with positive bboxes
            if line_obj.area >= 0:
                block_lines.append(line_obj)
        block_obj = Block(
            lines=block_lines,
            bbox=block["bbox"],
            pnum=pnum
        )
        # Only select blocks with lines
        if len(block_lines) > 0:
            page_blocks.append(block_obj)
    out_page = Page(
        blocks=page_blocks,
        pnum=page["page"],
        bbox=page["bbox"],
        rotation=page["rotation"],
    )
    return out_page


def get_text_blocks(doc, max_pages: Optional[int] = None) -> (List[Page], Dict):
    toc = get_toc(doc)

    page_range = range(len(doc))
    if max_pages:
        range_end = min(max_pages, len(doc))
        page_range = range(range_end)

    all_blocks = dictionary_output(doc, page_range=page_range)
    all_blocks = [pdftext_format_to_blocks(page, pnum) for pnum, page in enumerate(all_blocks)]

    return all_blocks, toc


def naive_get_text(doc):
    full_text = ""
    for page_idx in range(len(doc)):
        page = doc.get_page(page_idx)
        text_page = page.get_textpage()
        full_text += text_page.get_text_bounded() + "\n"
    return full_text


def get_toc(doc, max_depth=15):
    toc = doc.get_toc(max_depth=max_depth)
    toc_list = []
    for item in toc:
        list_item = {
            "title": item.title,
            "level": item.level,
            "is_closed": item.is_closed,
            "n_kids": item.n_kids,
            "page_index": item.page_index,
            "view_mode": pdfium_i.ViewmodeToStr.get(item.view_mode),
            "view_pos": item.view_pos,
        }
        toc_list.append(list_item)
    return toc_list


def get_length_of_text(fname: str) -> int:
    doc = pdfium.PdfDocument(fname)
    text = naive_get_text(doc).strip()

    return len(text)
