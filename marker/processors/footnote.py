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

    def __call__(self, document: Document):
        for page in document.pages:
            self.push_footnotes_to_bottom(page, document)


    def push_footnotes_to_bottom(self, page: PageGroup, document: Document):
        footnote_blocks = page.contained_blocks(document, self.block_types)

        # Push footnotes to the bottom
        for block in footnote_blocks:
            # Check if it is top-level
            if block.id in page.structure:
                # Move to bottom if it is
                page.structure.remove(block.id)
                page.add_structure(block)