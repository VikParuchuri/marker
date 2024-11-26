import re
from collections import Counter
from statistics import mean

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Footnote
from marker.schema.document import Document

from rapidfuzz import fuzz

from marker.schema.groups import PageGroup


class FootnoteProcessor(BaseProcessor):
    """
    A processor for pushing footnotes to the bottom, and relabeling mislabeled text blocks.

    Attributes:
        page_bottom_threshold (float):
            The fraction of page height that is considered the bottom.
            Default is .8

        line_height_scaler (float):
            The amount to scale line height by to consider a block a footnote. (from N to 1+(1-N))
            Default is .99
    """
    block_types = (BlockTypes.Footnote,)
    page_bottom_threshold = .75
    line_height_scaler = .99


    def __call__(self, document: Document):
        footnote_heights = self.compute_block_stats(document)
        if len(footnote_heights) == 0:
            footnote_heights = [999]

        avg_footnote_height = mean(footnote_heights)
        for page in document.pages:
            self.relabel_texts_to_footnotes(page, document, avg_footnote_height)
            self.push_footnotes_to_bottom(page, document)

    def compute_block_stats(self, document: Document):
        line_heights = []
        for page in document.pages:
            for footnote in page.contained_blocks(document, self.block_types):
                contained_lines = footnote.contained_blocks(document, (BlockTypes.Line,))
                line_heights.extend([line.polygon.height for line in contained_lines])
        return line_heights


    def relabel_texts_to_footnotes(self, page: PageGroup, document: Document, avg_footnote_height: int):
        text_blocks = page.contained_blocks(document, (BlockTypes.Text,))
        block_stats = []

        for block in text_blocks:
            contained_lines = block.contained_blocks(document, (BlockTypes.Line,))
            line_heights = [line.polygon.height for line in contained_lines]

            block_stats.append({
                "line_height": mean(line_heights) if len(line_heights) > 0 else 999,
                "in_bottom": block.polygon.y_end > page.polygon.height * self.page_bottom_threshold
            })

        # Find the average font size and line height
        if len(block_stats) == 0:
            return

        height_gap = 1 - self.line_height_scaler
        for text_block, stats_dict in zip(text_blocks, block_stats):
            if all([
                avg_footnote_height * self.line_height_scaler < stats_dict["line_height"] < avg_footnote_height * (1 + height_gap),
                stats_dict["in_bottom"]
            ]):
                new_block = Footnote.from_block(text_block)
                page.replace_block(text_block, new_block)


    def push_footnotes_to_bottom(self, page: PageGroup, document: Document):
        footnote_blocks = page.contained_blocks(document, self.block_types)

        # Push footnotes to the bottom
        for block in footnote_blocks:
            # Check if it is top-level
            if block.id in page.structure:
                # Move to bottom if it is
                page.structure.remove(block.id)
                page.add_structure(block)