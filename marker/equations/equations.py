from copy import deepcopy
from typing import List

from marker.debug.data import dump_equation_debug_data
from marker.equations.images import get_equation_image
from marker.equations.inference import get_total_texify_tokens, get_latex_batched
from marker.schema.page import Page
from marker.schema.block import Line, Span, Block
from marker.settings import settings


def find_equation_blocks(page, processor):
    equation_blocks = []
    for i in range(len(page.blocks)):
        block = page.blocks[i]
        block_text = block.prelim_text
        # Check if the block is an equation
        if not block.block_type in ["Formula"]:
            continue

        total_tokens = get_total_texify_tokens(block_text, processor)
        selected_blocks = (i, total_tokens)
        if total_tokens < settings.TEXIFY_MODEL_MAX:
            equation_blocks.append(selected_blocks)

    return equation_blocks


def replace_blocks_with_latex(page_blocks: Page, page_equation_blocks, predictions, pnum, processor):
    converted_spans = []
    idx = 0
    success_count = 0
    fail_count = 0
    for block_number, (block_idx, token_count) in enumerate(page_equation_blocks):
        block = page_blocks.blocks[block_idx]
        orig_block_text = block.prelim_text
        latex_text = predictions[block_number]
        conditions = [
            len(latex_text) > 0,
            get_total_texify_tokens(latex_text, processor) < settings.TEXIFY_MODEL_MAX,  # Make sure we didn't run to the overall token max
            len(latex_text) > len(orig_block_text) * .8,
            len(latex_text.strip()) > 0
        ]

        if not all(conditions):
            fail_count += 1
        else:
            success_count += 1
            block_line = Line(
                spans=[
                    Span(
                        text=latex_text,
                        bbox=block.bbox,
                        span_id=f"{pnum}_{idx}_fixeq",
                        font="Latex",
                        font_weight=0,
                        font_size=0
                    )
                ],
                bbox=block.bbox
            )
            block.lines = [block_line]
            converted_spans.append(deepcopy(block_line.spans[0]))

    return success_count, fail_count, converted_spans


def replace_equations(doc, pages: List[Page], texify_model, batch_size=settings.TEXIFY_BATCH_SIZE):
    unsuccessful_ocr = 0
    successful_ocr = 0

    # Find potential equation regions, and length of text in each region
    equation_blocks = []
    for pnum, page in enumerate(pages):
        equation_blocks.append(find_equation_blocks(page, texify_model.processor))

    eq_count = sum([len(x) for x in equation_blocks])

    images = []
    token_counts = []
    for page_idx, page_equation_blocks in enumerate(equation_blocks):
        page_obj = doc[page_idx]
        for equation_idx, (block_idx, token_count) in enumerate(page_equation_blocks):
            bbox = pages[page_idx].blocks[block_idx].bbox
            png_image = get_equation_image(page_obj, pages[page_idx], bbox)

            images.append(png_image)
            token_counts.append(token_count)

    # Make batched predictions
    predictions = get_latex_batched(images, token_counts, texify_model, batch_size)

    # Replace blocks with predictions
    page_start = 0
    converted_spans = []
    for page_idx, page_equation_blocks in enumerate(equation_blocks):
        page_equation_count = len(page_equation_blocks)
        page_predictions = predictions[page_start:page_start + page_equation_count]
        success_count, fail_count, converted_span = replace_blocks_with_latex(
            pages[page_idx],
            page_equation_blocks,
            page_predictions,
            page_idx,
            texify_model.processor
        )
        converted_spans.extend(converted_span)
        page_start += page_equation_count
        successful_ocr += success_count
        unsuccessful_ocr += fail_count

    # If debug mode is on, dump out conversions for comparison
    dump_equation_debug_data(doc, images, converted_spans)

    return pages, {"successful_ocr": successful_ocr, "unsuccessful_ocr": unsuccessful_ocr, "equations": eq_count}
