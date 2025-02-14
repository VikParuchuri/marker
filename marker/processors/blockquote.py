from typing import Annotated, Tuple

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class BlockquoteProcessor(BaseProcessor):
    """
    A processor for tagging blockquotes.
    """
    block_types: Annotated[
        Tuple[BlockTypes],
        "The block types to process.",
    ] = (BlockTypes.Text, BlockTypes.TextInlineMath)
    min_x_indent: Annotated[
        float,
        "The minimum horizontal indentation required to consider a block as part of a blockquote.",
        "Expressed as a percentage of the block width.",
    ] = 0.1
    x_start_tolerance: Annotated[
        float,
        "The maximum allowable difference between the starting x-coordinates of consecutive blocks to consider them aligned.",
        "Expressed as a percentage of the block width.",
    ] = 0.01
    x_end_tolerance: Annotated[
        float,
        "The maximum allowable difference between the ending x-coordinates of consecutive blocks to consider them aligned.",
        "Expressed as a percentage of the block width.",
    ] = 0.01

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if block.structure is None:
                    continue

                if not len(block.structure) >= 2:
                    continue

                next_block = page.get_next_block(block)
                if next_block is None:
                    continue
                if next_block.block_type not in self.block_types:
                    continue
                if next_block.structure is None:
                    continue
                if next_block.ignore_for_output:
                    continue

                matching_x_end = abs(next_block.polygon.x_end - block.polygon.x_end) < self.x_end_tolerance * block.polygon.width
                matching_x_start = abs(next_block.polygon.x_start - block.polygon.x_start) < self.x_start_tolerance * block.polygon.width
                x_indent = next_block.polygon.x_start > block.polygon.x_start + (self.min_x_indent * block.polygon.width)
                y_indent = next_block.polygon.y_start > block.polygon.y_end

                if block.blockquote:
                    next_block.blockquote = (matching_x_end and matching_x_start) or (x_indent and y_indent)
                    next_block.blockquote_level = block.blockquote_level
                    if (x_indent and y_indent):
                        next_block.blockquote_level += 1
                elif len(next_block.structure) >= 2 and (x_indent and y_indent):
                    next_block.blockquote = True
                    next_block.blockquote_level = 1