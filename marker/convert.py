import fitz as pymupdf

from marker.cleaners.table import merge_table_blocks, create_new_tables
from marker.extract_text import get_text_blocks
from marker.cleaners.headers import filter_header_footer, filter_common_titles
from marker.cleaners.equations import replace_equations
from marker.segmentation import detect_all_block_types
from marker.cleaners.code import identify_code_blocks, indent_blocks
from marker.markdown import merge_spans, merge_lines, get_full_text
from marker.schema import Page, BlockType
from typing import List, Dict, Tuple
from copy import deepcopy
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
    full_text = ""
    for page in doc:
        full_text += page.get_text("text", sort=True, flags=settings.TEXT_FLAGS)

    return len(full_text)


def convert_single_pdf(fname: str, layoutlm_model, nougat_model, max_pages=None, metadata: Dict | None=None) -> Tuple[str, Dict]:
    lang = settings.DEFAULT_LANG
    if metadata:
        lang = metadata.get("language", settings.DEFAULT_LANG)

    # Use tesseract language if available
    tess_lang = settings.TESSERACT_LANGUAGES.get(lang, settings.DEFAULT_LANG)
    spell_lang = settings.SPELLCHECK_LANGUAGES.get(lang)
    if "eng" not in tess_lang:
        tess_lang = f"eng+{tess_lang}"

    # Output metadata
    out_meta = {"lang": lang}

    filetype = find_filetype(fname)
    if filetype == "other":
        return "", out_meta

    out_meta["filetype"] = filetype

    doc = pymupdf.open(fname, filetype=filetype)
    if filetype != "pdf":
        conv = doc.convert_to_pdf()
        doc = pymupdf.open("pdf", conv)

    blocks, toc, ocr_stats = get_text_blocks(doc, tess_lang, spell_lang, max_pages=max_pages)

    out_meta["toc"] = toc
    out_meta["pages"] = len(blocks)
    out_meta["ocr_stats"] = ocr_stats
    if len([b for p in blocks for b in p.blocks]) == 0:
        print(f"Could not extract any text blocks for {fname}")
        return "", out_meta

    block_types = detect_all_block_types(doc, blocks, layoutlm_model)

    # Find headers and footers
    bad_span_ids = filter_header_footer(blocks)
    out_meta["block_stats"] = {"header_footer": len(bad_span_ids)}

    filtered = deepcopy(blocks)
    annotate_spans(filtered, block_types)

    # Fix code blocks
    code_block_count = identify_code_blocks(filtered)
    out_meta["block_stats"]["code"] = code_block_count
    indent_blocks(filtered)

    # Fix table blocks
    merge_table_blocks(filtered)
    table_count = create_new_tables(filtered)
    out_meta["block_stats"]["table"] = table_count

    for page in filtered:
        for block in page.blocks:
            block.filter_spans(bad_span_ids)
            block.filter_bad_span_types()

    filtered, eq_stats = replace_equations(doc, filtered, block_types, nougat_model)
    out_meta["block_stats"]["equations"] = eq_stats

    # Copy to avoid changing original data
    merged_lines = merge_spans(filtered)
    text_blocks = merge_lines(merged_lines, filtered)
    text_blocks = filter_common_titles(text_blocks)
    full_text = get_full_text(text_blocks)

    # Handle empty blocks being joined
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)

    return full_text, out_meta