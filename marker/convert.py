import fitz as pymupdf

from marker.cleaners.table import merge_table_blocks, create_new_tables
from marker.extract_text import get_text_blocks
from marker.cleaners.headers import categorize_blocks, filter_header_footer
from marker.cleaners.equations import replace_equations
from marker.segmentation import detect_all_block_types
from marker.cleaners.code import identify_code_blocks, indent_blocks
from marker.markdown import merge_spans, merge_lines, get_full_text
from marker.schema import Page, BlockType
from typing import List
from copy import deepcopy


def annotate_spans(blocks: List[Page], block_types: List[BlockType]):
    for i, page in enumerate(blocks):
        page_block_types = block_types[i]
        page.add_block_types(page_block_types)


def convert_single_pdf(fname: str, layoutlm_model, nougat_model):
    doc = pymupdf.open(fname)
    blocks, toc = get_text_blocks(doc)

    block_types = detect_all_block_types(doc, blocks, layoutlm_model)

    # Find headers and footers
    bad_span_ids = categorize_blocks(blocks)
    bad_span_ids += filter_header_footer(blocks)

    filtered = deepcopy(blocks)
    annotate_spans(filtered, block_types)

    # Fix code blocks
    identify_code_blocks(filtered)
    indent_blocks(filtered)

    # Fix table blocks
    merge_table_blocks(filtered)
    create_new_tables(filtered)

    for page in filtered:
        for block in page.blocks:
            block.filter_spans(bad_span_ids)
            block.filter_bad_span_types(block_types[page.pnum])

    filtered = replace_equations(doc, filtered, block_types, nougat_model)

    # Copy to avoid changing original data
    merged_lines = merge_spans(filtered)
    text_blocks = merge_lines(merged_lines, filtered)
    full_text = get_full_text(text_blocks)

    return full_text