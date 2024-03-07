import fitz as pymupdf

from marker.cleaners.table import merge_table_blocks, create_new_tables
from marker.debug.data import dump_bbox_debug_data
from marker.extract_text import get_text_blocks
from marker.cleaners.headers import filter_header_footer, filter_common_titles
from marker.cleaners.equations import replace_equations
from marker.ordering import order_blocks
from marker.postprocessors.editor import edit_full_text
from marker.segmentation import detect_document_block_types
from marker.cleaners.code import identify_code_blocks, indent_blocks
from marker.cleaners.bullets import replace_bullets
from marker.markdown import merge_spans, merge_lines, get_full_text
from marker.schema import Page, BlockType
from typing import List, Dict, Tuple, Optional
import re
import magic
from marker.settings import settings


def find_filetype(fpath):
    mimetype = magic.from_file(fpath).lower()

    # Get extensions from mimetype
    # The mimetype is not always consistent, so use in to check the most common formats
    if "pdf" in mimetype:
        return "pdf"
    elif "epub" in mimetype:
        return "epub"
    elif "mobi" in mimetype:
        return "mobi"
    elif mimetype in settings.SUPPORTED_FILETYPES:
        return settings.SUPPORTED_FILETYPES[mimetype]
    else:
        print(f"Found nonstandard filetype {mimetype}")
        return "other"


def annotate_spans(blocks: List[Page], block_types: List[BlockType]):
    for i, page in enumerate(blocks):
        page_block_types = block_types[i]
        page.add_block_types(page_block_types)


def get_length_of_text(fname: str) -> int:
    filetype = find_filetype(fname)
    if filetype == "other":
        return 0

    doc = pymupdf.open(fname, filetype=filetype)
    count = 0
    for page in doc:
        count += len(page.get_text("text", sort=True, flags=settings.TEXT_FLAGS))

    return count


def convert_single_pdf(
        fname: str,
        model_lst: List,
        max_pages=None,
        metadata: Optional[Dict]=None,
        parallel_factor: int = 1
) -> Tuple[str, Dict]:
    lang = settings.DEFAULT_LANG
    if metadata:
        lang = metadata.get("language", settings.DEFAULT_LANG)

    # Use tesseract language if available
    tess_lang = settings.TESSERACT_LANGUAGES.get(lang, "eng")
    spell_lang = settings.SPELLCHECK_LANGUAGES.get(lang, None)
    if "eng" not in tess_lang:
        tess_lang = f"eng+{tess_lang}"

    # Output metadata
    out_meta = {"language": lang}

    filetype = find_filetype(fname)
    if filetype == "other":
        return "", out_meta

    out_meta["filetype"] = filetype

    doc = pymupdf.open(fname, filetype=filetype)
    if filetype != "pdf":
        conv = doc.convert_to_pdf()
        doc = pymupdf.open("pdf", conv)

    blocks, toc, ocr_stats = get_text_blocks(
        doc,
        tess_lang,
        spell_lang,
        max_pages=max_pages,
        parallel=int(parallel_factor * settings.OCR_PARALLEL_WORKERS)
    )

    out_meta["toc"] = toc
    out_meta["pages"] = len(blocks)
    out_meta["ocr_stats"] = ocr_stats
    if len([b for p in blocks for b in p.blocks]) == 0:
        print(f"Could not extract any text blocks for {fname}")
        return "", out_meta

    # Unpack models from list
    texify_model, layoutlm_model, order_model, edit_model = model_lst

    block_types = detect_document_block_types(
        doc,
        blocks,
        layoutlm_model,
        batch_size=int(settings.LAYOUT_BATCH_SIZE * parallel_factor)
    )

    # Find headers and footers
    bad_span_ids = filter_header_footer(blocks)
    out_meta["block_stats"] = {"header_footer": len(bad_span_ids)}

    annotate_spans(blocks, block_types)

    # Dump debug data if flags are set
    dump_bbox_debug_data(doc, blocks)

    blocks = order_blocks(
        doc,
        blocks,
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
