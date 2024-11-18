from collections import Counter

from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document


class IgnoreTextProcessor(BaseProcessor):
    block_types = (BlockTypes.Text,)
    common_element_threshold = .6
    max_blocks = 1

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
