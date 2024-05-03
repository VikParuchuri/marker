from collections import defaultdict
from copy import deepcopy
from typing import List

from marker.debug.data import dump_equation_debug_data
from marker.equations.images import get_equation_image
from marker.equations.inference import get_total_texify_tokens, get_latex_batched
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.schema.block import Line, Span, Block, bbox_from_lines
from marker.settings import settings


def find_equation_blocks(page, processor):
    equation_blocks = []
    equation_regions = [l.bbox for l in page.layout.bboxes if l.label in ["Formula"]]
    equation_regions = [rescale_bbox(page.layout.image_bbox, page.bbox, b) for b in equation_regions]

    lines_to_remove = defaultdict(list)
    insert_points = {}
    equation_lines = defaultdict(list)
    for region_idx, region in enumerate(equation_regions):
        for block_idx, block in enumerate(page.blocks):
            for line_idx, line in enumerate(block.lines):
                if line.intersection_pct(region) > .8:
                    # We will remove this line from the block
                    lines_to_remove[region_idx].append((block_idx, line_idx))
                    equation_lines[region_idx].append(line)

                    if region_idx not in insert_points:
                        # Insert before the block if line is at the beginning of the block, otherwise after the block
                        if line_idx <= len(block.lines) // 2:
                            insert_points[region_idx] = block_idx
                        else:
                            insert_points[region_idx] = block_idx + 1

    block_lines_to_remove = defaultdict(set)
    for region_idx, equation_region in enumerate(equation_regions):
        if region_idx not in equation_lines or len(equation_lines[region_idx]) == 0:
            continue
        equation_block = equation_lines[region_idx]
        equation_insert = insert_points[region_idx]
        block_text = " ".join([line.prelim_text for line in equation_block])
        equation_bbox = bbox_from_lines(equation_block)

        total_tokens = get_total_texify_tokens(block_text, processor)
        selected_blocks = (equation_insert, total_tokens, block_text, equation_bbox)
        if total_tokens < settings.TEXIFY_MODEL_MAX:
            for item in lines_to_remove[region_idx]:
                block_lines_to_remove[item[0]].add(item[1])
            equation_blocks.append(selected_blocks)

    # Remove the lines from the blocks
    for block_idx, bad_lines in block_lines_to_remove.items():
        block = page.blocks[block_idx]
        block.lines = [line for idx, line in enumerate(block.lines) if idx not in bad_lines]

    return equation_blocks


def insert_latex_block(page_blocks: Page, page_equation_blocks, predictions, pnum, processor):
    converted_spans = []
    idx = 0
    success_count = 0
    fail_count = 0
    for block_number, (insert_point, token_count, block_text, equation_bbox) in enumerate(page_equation_blocks):
        latex_text = predictions[block_number]
        conditions = [
            get_total_texify_tokens(latex_text, processor) < settings.TEXIFY_MODEL_MAX,  # Make sure we didn't get to the overall token max, indicates run-on
            len(latex_text) > len(block_text) * .7,
            len(latex_text.strip()) > 0
        ]

        new_block = Block(
            lines=[Line(
                spans=[
                    Span(
                        text=block_text.replace("\n", " "),
                        bbox=equation_bbox,
                        span_id=f"{pnum}_{idx}_fixeq",
                        font="Latex",
                        font_weight=0,
                        font_size=0
                    )
                ],
                bbox=equation_bbox
            )],
            bbox=equation_bbox,
            block_type="Formula",
            pnum=pnum
        )

        if not all(conditions):
            fail_count += 1
        else:
            success_count += 1
            new_block.lines[0].spans[0].text = latex_text
            converted_spans.append(deepcopy(new_block.lines[0].spans[0]))

        page_blocks.blocks.insert(insert_point, new_block)

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
        for equation_idx, (insert_idx, token_count, block_text, equation_bbox) in enumerate(page_equation_blocks):
            png_image = get_equation_image(page_obj, pages[page_idx], equation_bbox)

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
        success_count, fail_count, converted_span = insert_latex_block(
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
