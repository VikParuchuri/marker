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
    """
    block_types = (BlockTypes.Footnote,)
    page_bottom_threshold = .66
    font_size_scaler = .5
    line_height_scaler = .5

    def __call__(self, document: Document):
        for page in document.pages:
            self.relabel_texts_to_footnotes(page, document)
            self.push_footnotes_to_bottom(page, document)


    def relabel_texts_to_footnotes(self, page: PageGroup, document: Document):
        text_blocks = page.contained_blocks(document, (BlockTypes.Text,))
        block_stats = []

        for block in text_blocks:
            contained_spans = block.contained_blocks(document, (BlockTypes.Span,))
            font_size = [span.font_size for span in contained_spans]
            contained_lines = block.contained_blocks(document, (BlockTypes.Line,))
            line_heights = [line.polygon.height for line in contained_lines]

            block_stats.append({
                "font_size": mean(font_size),
                "line_height": mean(line_heights),
                "line_heights": line_heights,
                "font_sizes": font_size,
                "in_bottom_third": block.polygon.y_end > page.polygon.height * self.page_bottom_threshold
            })

        # Find the average font size and line height
        avg_font_size = mean([fs for bs in block_stats for fs in bs["font_sizes"]])
        avg_line_height = mean([lh for bs in block_stats for lh in bs["line_heights"]])

        for text_block, stats_dict in zip(text_blocks, block_stats):
            if all([
                stats_dict["font_size"] < avg_font_size * self.font_size_scaler,
                stats_dict["line_height"] < avg_line_height * self.line_height_scaler,
                stats_dict["in_bottom_third"]
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