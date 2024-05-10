from collections import defaultdict
from copy import deepcopy
from typing import List

from marker.debug.data import dump_equation_debug_data
from marker.equations.inference import get_total_texify_tokens, get_latex_batched
from marker.pdf.images import render_bbox_image
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.schema.block import Line, Span, Block, bbox_from_lines, split_block_lines, find_insert_block
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
                if line.intersection_pct(region) > settings.BBOX_INTERSECTION_THRESH:
                    # We will remove this line from the block
                    lines_to_remove[region_idx].append((block_idx, line_idx))
                    equation_lines[region_idx].append(line)

                    if region_idx not in insert_points:
                        insert_points[region_idx] = (block_idx, line_idx)

    # Account for regions where the lines were not detected
    for region_idx, region in enumerate(equation_regions):
        if region_idx in insert_points:
            continue

        insert_points[region_idx] = (find_insert_block(page.blocks, region), 0)

    block_lines_to_remove = defaultdict(set)
    for region_idx, equation_region in enumerate(equation_regions):
        if region_idx not in equation_lines or len(equation_lines[region_idx]) == 0:
            block_text = ""
            total_tokens = 0
        else:
            equation_block = equation_lines[region_idx]
            block_text = " ".join([line.prelim_text for line in equation_block])
            total_tokens = get_total_texify_tokens(block_text, processor)

        equation_insert = insert_points[region_idx]
        equation_insert_line_idx = equation_insert[1]
        equation_insert_line_idx -= len(
            [x for x in lines_to_remove[region_idx] if x[0] == equation_insert[0] and x[1] < equation_insert[1]])

        selected_blocks = [equation_insert[0], equation_insert_line_idx, total_tokens, block_text, equation_region]
        if total_tokens < settings.TEXIFY_MODEL_MAX:
            # Account for the lines we're about to remove
            for item in lines_to_remove[region_idx]:
                block_lines_to_remove[item[0]].add(item[1])
            equation_blocks.append(selected_blocks)

    # Remove the lines from the blocks
    for block_idx, bad_lines in block_lines_to_remove.items():
        block = page.blocks[block_idx]
        block.lines = [line for idx, line in enumerate(block.lines) if idx not in bad_lines]

    return equation_blocks


def increment_insert_points(page_equation_blocks, insert_block_idx, insert_count):
    for idx, (block_idx, line_idx, token_count, block_text, equation_bbox) in enumerate(page_equation_blocks):
        if block_idx >= insert_block_idx:
            page_equation_blocks[idx][0] += insert_count


def insert_latex_block(page_blocks: Page, page_equation_blocks, predictions, pnum, processor):
    converted_spans = []
    idx = 0
    success_count = 0
    fail_count = 0
    for block_number, (insert_block_idx, insert_line_idx, token_count, block_text, equation_bbox) in enumerate(page_equation_blocks):
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
            new_block.lines[0].spans[0].text = latex_text.replace("\n", " ")
            converted_spans.append(deepcopy(new_block.lines[0].spans[0]))

        # Add in the new LaTeX block
        if insert_line_idx == 0:
            page_blocks.blocks.insert(insert_block_idx, new_block)
            increment_insert_points(page_equation_blocks, insert_block_idx, 1)
        elif insert_line_idx >= len(page_blocks.blocks[insert_block_idx].lines):
            page_blocks.blocks.insert(insert_block_idx + 1, new_block)
            increment_insert_points(page_equation_blocks, insert_block_idx + 1, 1)
        else:
            new_blocks = []
            for block_idx, block in enumerate(page_blocks.blocks):
                if block_idx == insert_block_idx:
                    split_block = split_block_lines(block, insert_line_idx)
                    new_blocks.append(split_block[0])
                    new_blocks.append(new_block)
                    new_blocks.append(split_block[1])
                    increment_insert_points(page_equation_blocks, insert_block_idx, 2)
                else:
                    new_blocks.append(block)
            page_blocks.blocks = new_blocks

    return success_count, fail_count, converted_spans


def replace_equations(doc, pages: List[Page], texify_model, batch_multiplier=1):
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
        for equation_idx, (insert_block_idx, insert_line_idx, token_count, block_text, equation_bbox) in enumerate(page_equation_blocks):
            png_image = render_bbox_image(page_obj, pages[page_idx], equation_bbox)

            images.append(png_image)
            token_counts.append(token_count)

    # Make batched predictions
    predictions = get_latex_batched(images, token_counts, texify_model, batch_multiplier=batch_multiplier)

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
