from typing import List

from marker.settings import settings
from marker.schema.bbox import rescale_bbox
from marker.schema.block import bbox_from_lines
from marker.schema.page import Page


def split_heading_blocks(pages: List[Page]):
    # Heading lines can be combined into regular text blocks sometimes by pdftext
    # Split up heading lines into separate blocks properly
    for page in pages:
        page_heading_boxes = [b for b in page.layout.bboxes if b.label in ["Title", "Section-header"]]
        page_heading_boxes = [(rescale_bbox(page.layout.image_bbox, page.bbox, b.bbox), b.label) for b in page_heading_boxes]

        new_blocks = []
        for block_idx, block in enumerate(page.blocks):
            if block.block_type not in ["Text"]:
                new_blocks.append(block)
                continue

            heading_lines = []
            for line_idx, line in enumerate(block.lines):
                for (heading_box, label) in page_heading_boxes:
                    if line.intersection_pct(heading_box) > settings.BBOX_INTERSECTION_THRESH:
                        heading_lines.append((line_idx, label))
                        break

            if len(heading_lines) == 0:
                new_blocks.append(block)
                continue

            # Split up the block into separate blocks around headers
            start = 0
            for (heading_line, label) in heading_lines:
                if start < heading_line:
                    copied_block = block.copy()
                    copied_block.lines = block.lines[start:heading_line]
                    copied_block.bbox = bbox_from_lines(copied_block.lines)
                    new_blocks.append(copied_block)

                copied_block = block.copy()
                copied_block.lines = block.lines[heading_line:heading_line + 1]
                copied_block.block_type = label
                copied_block.bbox = bbox_from_lines(copied_block.lines)
                new_blocks.append(copied_block)

                start = heading_line + 1
                if start >= len(block.lines):
                    break

            # Add any remaining lines
            if start < len(block.lines):
                copied_block = block.copy()
                copied_block.lines = block.lines[start:]
                copied_block.bbox = bbox_from_lines(copied_block.lines)
                new_blocks.append(copied_block)

        page.blocks = new_blocks
