import io
from copy import deepcopy
from functools import partial
from typing import List

import torch
from texify.inference import batch_inference
from texify.model.model import load_model
from texify.model.processor import load_processor
import re
from PIL import Image, ImageDraw

from marker.bbox import should_merge_blocks, merge_boxes
from marker.debug.data import dump_equation_debug_data
from marker.settings import settings
from marker.schema import Page, Span, Line, Block, BlockType
import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"

processor = load_processor()


def load_texify_model():
    texify_model = load_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=settings.TORCH_DEVICE_MODEL, dtype=settings.TEXIFY_DTYPE)
    return texify_model


def mask_bbox(png_image, bbox, selected_bboxes):
    mask = Image.new('L', png_image.size, 0)  # 'L' mode for grayscale
    draw = ImageDraw.Draw(mask)
    first_x = bbox[0]
    first_y = bbox[1]
    bbox_height = bbox[3] - bbox[1]
    bbox_width = bbox[2] - bbox[0]

    for box in selected_bboxes:
        # Fit the box to the selected region
        new_box = (box[0] - first_x, box[1] - first_y, box[2] - first_x, box[3] - first_y)
        # Fit mask to image bounds versus the pdf bounds
        resized = (
           new_box[0] / bbox_width * png_image.size[0],
           new_box[1] / bbox_height * png_image.size[1],
           new_box[2] / bbox_width * png_image.size[0],
           new_box[3] / bbox_height * png_image.size[1]
        )
        draw.rectangle(resized, fill=255)

    result = Image.composite(png_image, Image.new('RGBA', png_image.size, 'white'), mask)
    return result


def get_masked_image(page, bbox, selected_bboxes):
    pix = page.get_pixmap(dpi=settings.TEXIFY_DPI, clip=bbox)
    png = pix.pil_tobytes(format="PNG")
    png_image = Image.open(io.BytesIO(png))
    png_image = mask_bbox(png_image, bbox, selected_bboxes)
    png_image = png_image.convert("RGB")
    return png_image


def get_latex_batched(images, reformat_region_lens, texify_model, batch_size):
    if len(images) == 0:
        return []

    predictions = [""] * len(images)

    for i in range(0, len(images), batch_size):
        # Dynamically set max length to save inference time
        min_idx = i
        max_idx = min(min_idx + batch_size, len(images))
        max_length = max(reformat_region_lens[min_idx:max_idx])
        max_length = min(max_length, settings.TEXIFY_MODEL_MAX)
        max_length += settings.TEXIFY_TOKEN_BUFFER

        model_output = batch_inference(images[min_idx:max_idx], texify_model, processor, max_tokens=max_length)

        for j, output in enumerate(model_output):
            token_count = get_total_texify_tokens(output)
            if token_count >= max_length - 1:
                output = ""

            image_idx = i + j
            predictions[image_idx] = output
    return predictions


def get_total_texify_tokens(text):
    tokenizer = processor.tokenizer
    tokens = tokenizer(text)
    return len(tokens["input_ids"])


def find_page_equation_regions(pnum, page, block_types):
    i = 0
    equation_boxes = [b.bbox for b in block_types[pnum] if b.block_type == "Formula"]
    reformatted_blocks = set()
    reformat_regions = []
    block_lens = []
    while i < len(page.blocks):
        block = page.blocks[i]
        block_text = block.prelim_text
        bbox = block.bbox
        # Check if the block contains an equation
        if not block.contains_equation(equation_boxes):
            i += 1
            continue

        selected_blocks = [(i, block)]
        if i > 0:
            # Find previous blocks to merge
            j = i - 1
            prev_block = page.blocks[j]
            prev_bbox = prev_block.bbox
            while (should_merge_blocks(prev_bbox, bbox) or prev_block.contains_equation(equation_boxes)) \
                    and j >= 0 \
                    and j not in reformatted_blocks:
                bbox = merge_boxes(prev_bbox, bbox)
                prev_block = page.blocks[j]
                prev_bbox = prev_block.bbox
                prelim_block_text = prev_block.prelim_text + " " + block_text
                if get_total_texify_tokens(prelim_block_text) >= settings.TEXIFY_MODEL_MAX:
                    break

                block_text = prelim_block_text
                selected_blocks.append((j, prev_block))
                j -= 1

        if i < len(page.blocks) - 1:
            # Merge subsequent boxes
            next_block = page.blocks[i + 1]
            next_bbox = next_block.bbox
            while (should_merge_blocks(bbox, next_bbox) or next_block.contains_equation(
                    equation_boxes)) and i + 1 < len(page.blocks):
                bbox = merge_boxes(bbox, next_bbox)
                prelim_block_text = block_text + " " + next_block.prelim_text
                if get_total_texify_tokens(prelim_block_text) >= settings.TEXIFY_MODEL_MAX:
                    break

                block_text = prelim_block_text
                i += 1
                selected_blocks.append((i, next_block))
                if i + 1 < len(page.blocks):
                    next_block = page.blocks[i + 1]
                    next_bbox = next_block.bbox

        total_tokens = get_total_texify_tokens(block_text)
        ordered_blocks = sorted(([sb[0] for sb in selected_blocks]))
        if total_tokens < settings.TEXIFY_MODEL_MAX:
            # Get indices of all blocks to merge
            reformat_regions.append(ordered_blocks)
            block_lens.append(total_tokens)
            reformatted_blocks.update(ordered_blocks)
        else:
            # Reset i to the original value
            i = selected_blocks[0][0]

        i += 1

    return reformat_regions, block_lens


def get_bboxes_for_region(page, region):
    bboxes = []
    merged_box = None
    for idx in region:
        block = page.blocks[idx]
        bbox = block.bbox
        if merged_box is None:
            merged_box = bbox
        else:
            merged_box = merge_boxes(merged_box, bbox)
        bboxes.append(bbox)
    return bboxes, merged_box


def replace_blocks_with_latex(page_blocks: Page, merged_boxes, reformat_regions, predictions, pnum):
    new_blocks = []
    converted_spans = []
    current_region = 0
    idx = 0
    success_count = 0
    fail_count = 0
    while idx < len(page_blocks.blocks):
        block = page_blocks.blocks[idx]
        if current_region >= len(reformat_regions) or idx < reformat_regions[current_region][0]:
            new_blocks.append(block)
            idx += 1
            continue

        orig_block_text = " ".join([page_blocks.blocks[i].prelim_text for i in reformat_regions[current_region]])
        latex_text = predictions[current_region]
        conditions = [
            len(latex_text) > 0,
            get_total_texify_tokens(latex_text) < settings.TEXIFY_MODEL_MAX,  # Make sure we didn't run to the overall token max
            len(latex_text) > len(orig_block_text) * .8,
            len(latex_text.strip()) > 0
        ]

        idx = reformat_regions[current_region][-1] + 1
        if not all(conditions):
            fail_count += 1
            converted_spans.append(None)
            for i in reformat_regions[current_region]:
                new_blocks.append(page_blocks.blocks[i])
        else:
            success_count += 1
            block_line = Line(
                spans=[
                    Span(
                        text=latex_text,
                        bbox=merged_boxes[current_region],
                        span_id=f"{pnum}_{idx}_fixeq",
                        font="Latex",
                        color=0,
                        block_type="Formula"
                    )
                ],
                bbox=merged_boxes[current_region]
            )
            converted_spans.append(deepcopy(block_line.spans[0]))
            new_blocks.append(Block(
                lines=[block_line],
                bbox=merged_boxes[current_region],
                pnum=pnum
            ))
        current_region += 1
    return new_blocks, success_count, fail_count, converted_spans


def replace_equations(doc, blocks: List[Page], block_types: List[List[BlockType]], texify_model, batch_size=settings.TEXIFY_BATCH_SIZE):
    unsuccessful_ocr = 0
    successful_ocr = 0

    # Find potential equation regions, and length of text in each region
    reformat_regions = []
    reformat_region_lens = []
    for pnum, page in enumerate(blocks):
        regions, region_lens = find_page_equation_regions(pnum, page, block_types)
        reformat_regions.append(regions)
        reformat_region_lens.append(region_lens)

    eq_count = sum([len(x) for x in reformat_regions])

    # Get images for each region
    flat_reformat_region_lens = [item for sublist in reformat_region_lens for item in sublist]
    images = []
    merged_boxes = []
    for page_idx, reformat_regions_page in enumerate(reformat_regions):
        page_obj = doc[page_idx]
        for reformat_region in reformat_regions_page:
            bboxes, merged_box = get_bboxes_for_region(blocks[page_idx], reformat_region)
            png_image = get_masked_image(page_obj, merged_box, bboxes)
            images.append(png_image)
            merged_boxes.append(merged_box)

    # Make batched predictions
    predictions = get_latex_batched(images, flat_reformat_region_lens, texify_model, batch_size)

    # Replace blocks with predictions
    page_start = 0
    converted_spans = []
    for page_idx, reformat_regions_page in enumerate(reformat_regions):
        page_predictions = predictions[page_start:page_start + len(reformat_regions_page)]
        page_boxes = merged_boxes[page_start:page_start + len(reformat_regions_page)]
        new_page_blocks, success_count, fail_count, converted_span = replace_blocks_with_latex(
            blocks[page_idx],
            page_boxes,
            reformat_regions_page,
            page_predictions,
            page_idx
        )
        converted_spans.extend(converted_span)
        blocks[page_idx].blocks = new_page_blocks
        page_start += len(reformat_regions_page)
        successful_ocr += success_count
        unsuccessful_ocr += fail_count

    # If debug mode is on, dump out conversions for comparison
    dump_equation_debug_data(doc, images, converted_spans)

    return blocks, {"successful_ocr": successful_ocr, "unsuccessful_ocr": unsuccessful_ocr, "equations": eq_count}