from collections import defaultdict
from typing import List

from surya.layout import batch_layout_detection

from marker.pdf.images import render_image
from marker.schema.bbox import rescale_bbox
from marker.schema.block import bbox_from_lines
from marker.schema.page import Page
from marker.settings import settings


def get_batch_size():
    if settings.LAYOUT_BATCH_SIZE is not None:
        return settings.LAYOUT_BATCH_SIZE
    elif settings.TORCH_DEVICE_MODEL == "cuda":
        return 6
    return 6


def surya_layout(doc, pages: List[Page], layout_model, batch_multiplier=1):
    images = [render_image(doc[pnum], dpi=settings.SURYA_LAYOUT_DPI) for pnum in range(len(pages))]
    text_detection_results = [p.text_lines for p in pages]

    processor = layout_model.processor
    layout_results = batch_layout_detection(images, layout_model, processor, detection_results=text_detection_results, batch_size=int(get_batch_size() * batch_multiplier))
    for page, layout_result in zip(pages, layout_results):
        page.layout = layout_result


def annotate_block_types(pages: List[Page]):
    for page in pages:
        max_intersections = {}
        for i, block in enumerate(page.blocks):
            for j, layout_block in enumerate(page.layout.bboxes):
                layout_bbox = layout_block.bbox
                layout_bbox = rescale_bbox(page.layout.image_bbox, page.bbox, layout_bbox)
                intersection_pct = block.intersection_pct(layout_bbox)
                if i not in max_intersections:
                    max_intersections[i] = (intersection_pct, j)
                elif intersection_pct > max_intersections[i][0]:
                    max_intersections[i] = (intersection_pct, j)

        for i, block in enumerate(page.blocks):
            block = page.blocks[i]
            block_type = None
            if i in max_intersections and max_intersections[i][0] > 0.0:
                j = max_intersections[i][1]
                block_type = page.layout.bboxes[j].label
            block.block_type = block_type

        # Smarter block layout assignment - first assign same as closest block
        # Next, fall back to text
        for i, block in enumerate(page.blocks):
            if block.block_type is not None:
                continue
            min_dist = 0
            min_dist_idx = None
            for j, block2 in enumerate(page.blocks):
                if j == i or block2.block_type is None:
                    continue
                dist = block.distance(block2.bbox)
                if min_dist_idx is None or dist < min_dist:
                    min_dist = dist
                    min_dist_idx = j
                for line in block2.lines:
                    dist = block2.distance(line.bbox)
                    if min_dist_idx is None or dist < min_dist:
                        min_dist = dist
                        min_dist_idx = j

            if min_dist_idx is not None:
                block.block_type = page.blocks[min_dist_idx].block_type

        for i, block in enumerate(page.blocks):
            if block.block_type is None:
                block.block_type = "Text"

        # Merge blocks together, preserving pdf order
        curr_layout_idx = None
        curr_layout_block = None
        new_blocks = []
        for i in range(len(page.blocks)):
            if i not in max_intersections:
                if curr_layout_block is not None:
                    curr_layout_block.bbox = bbox_from_lines(curr_layout_block.lines)
                    new_blocks.append(curr_layout_block)
                curr_layout_block = None
                curr_layout_idx = None
                new_blocks.append(page.blocks[i])
            elif max_intersections[i][1] != curr_layout_idx:
                if curr_layout_block is not None:
                    curr_layout_block.bbox = bbox_from_lines(curr_layout_block.lines)
                    new_blocks.append(curr_layout_block)
                curr_layout_block = page.blocks[i].copy()
                curr_layout_idx = max_intersections[i][1]
            else:
                curr_layout_block.lines.extend(page.blocks[i].lines)

        if curr_layout_block is not None:
            curr_layout_block.bbox = bbox_from_lines(curr_layout_block.lines)
            new_blocks.append(curr_layout_block)

        page.blocks = new_blocks
