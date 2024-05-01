import pypdfium2 as pdfium

from marker.cleaners.table import merge_table_blocks, create_new_tables
from marker.debug.data import dump_bbox_debug_data
from marker.ocr.lang import replace_langs_with_codes, validate_langs
from marker.ocr.detection import surya_detection
from marker.ocr.recognition import run_ocr
from marker.pdf.extract_text import get_text_blocks
from marker.cleaners.headers import filter_header_footer, filter_common_titles
from marker.cleaners.equations import replace_equations
from marker.ordering import order_blocks
from marker.pdf.filetype import find_filetype
from marker.postprocessors.editor import edit_full_text
from marker.segmentation import detect_document_block_types
from marker.cleaners.code import identify_code_blocks, indent_blocks
from marker.cleaners.bullets import replace_bullets
from marker.markdown import merge_spans, merge_lines, get_full_text
from marker.schema.schema import BlockType
from marker.schema.page import Page
from typing import List, Dict, Tuple, Optional
import re
from marker.settings import settings


def annotate_spans(blocks: List[Page], block_types: List[BlockType]):
    for i, page in enumerate(blocks):
        page_block_types = block_types[i]
        page.add_block_types(page_block_types)


def convert_single_pdf(
        fname: str,
        model_lst: List,
        max_pages=None,
        metadata: Optional[Dict]=None,
        parallel_factor: int = 1
) -> Tuple[str, Dict]:
    # Set language needed for OCR
    langs = [settings.DEFAULT_LANG]
    if metadata:
        langs = metadata.get("languages", langs)

    langs = replace_langs_with_codes(langs)
    validate_langs(langs)

    # Find the filetype
    filetype = find_filetype(fname)

    # Setup output metadata
    out_meta = {
        "languages": langs,
        "filetype": filetype,
    }

    if filetype == "other": # We can't process this file
        return "", out_meta

    # Get initial text blocks from the pdf
    doc = pdfium.PdfDocument(fname)
    pages, toc = get_text_blocks(
        doc,
        max_pages=max_pages,
    )
    out_meta.update({
        "toc": toc,
        "pages": len(pages),
    })

    # Unpack models from list
    texify_model, layout_model, order_model, edit_model, detection_model, ocr_model = model_lst

    # Identify text lines on pages
    surya_detection(doc, pages, detection_model)

    # OCR pages as needed
    pages, ocr_stats = run_ocr(doc, pages, langs, ocr_model, parallel_factor)

    if len([b for p in pages for b in p.blocks]) == 0:
        print(f"Could not extract any text blocks for {fname}")
        return "", out_meta

    block_types = detect_document_block_types(
        doc,
        pages,
        layoutlm_model,
        batch_size=int(settings.LAYOUT_BATCH_SIZE * parallel_factor)
    )

    # Find headers and footers
    bad_span_ids = filter_header_footer(pages)
    out_meta["block_stats"] = {"header_footer": len(bad_span_ids)}

    annotate_spans(pages, block_types)

    # Dump debug data if flags are set
    dump_bbox_debug_data(doc, pages)

    blocks = order_blocks(
        doc,
        pages,
        order_model,
        batch_size=int(settings.ORDERER_BATCH_SIZE * parallel_factor)
    )

    # Fix code blocks
    code_block_count = identify_code_blocks(blocks)
    out_meta["block_stats"]["code"] = code_block_count
    indent_blocks(blocks)

    # Fix table blocks
    merge_table_blocks(blocks)
    table_count = create_new_tables(blocks)
    out_meta["block_stats"]["table"] = table_count

    for page in blocks:
        for block in page.blocks:
            block.filter_spans(bad_span_ids)
            block.filter_bad_span_types()

    filtered, eq_stats = replace_equations(
        doc,
        blocks,
        block_types,
        texify_model,
        batch_size=int(settings.TEXIFY_BATCH_SIZE * parallel_factor)
    )
    out_meta["block_stats"]["equations"] = eq_stats

    # Copy to avoid changing original data
    merged_lines = merge_spans(filtered)
    text_blocks = merge_lines(merged_lines, filtered)
    text_blocks = filter_common_titles(text_blocks)
    full_text = get_full_text(text_blocks)

    # Handle empty blocks being joined
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)

    # Replace bullet characters with a -
    full_text = replace_bullets(full_text)

    # Postprocess text with editor model
    full_text, edit_stats = edit_full_text(
        full_text,
        edit_model,
        batch_size=settings.EDITOR_BATCH_SIZE * parallel_factor
    )
    out_meta["postprocess_stats"] = {"edit": edit_stats}

    return full_text, out_meta