from collections import Counter

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class IgnoreTextProcessor(BaseProcessor):
    """
    A processor for ignoring text blocks that are common elements in the document.

    Attributes:
        common_element_threshold (float):
            The minimum fraction of pages that a block must appear in to be considered a common element.
            Default is 0.6.
    """
    block_types = (BlockTypes.Text,)
    common_element_threshold = .6

    def __call__(self, document: Document):
        first_blocks = []
        last_blocks = []
        for page in document.pages:
            initial_block = None
            block = None
            last_block = None
            for block in page.children:
                if block.block_type not in self.block_types:
                    continue

                if initial_block is None:
                    initial_block = block

            if block is not None:
                last_block = block

            if initial_block is not None:
                first_blocks.append(initial_block)
            if last_block is not None:
                last_blocks.append(last_block)

        self.filter_common_elements(document, first_blocks)
        self.filter_common_elements(document, last_blocks)

    def filter_common_elements(self, document, lines):
        # We can't filter if we don't have enough pages to find common elements
        if len(lines) < 3:
            return []

        text = [b.raw_text(document) for b in lines]
        counter = Counter(text)
        common = [k for k, v in counter.items() if v > len(lines) * self.common_element_threshold]
        for b in lines:
            if b.raw_text(document) in common:
                b.is_header_footer = True
