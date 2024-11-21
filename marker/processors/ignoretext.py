import re
from collections import Counter

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


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
            for block in page.contained_blocks(document, self.block_types):
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

    @staticmethod
    def clean_text(text):
        return re.sub(r"\s+", "", text)

    def filter_common_elements(self, document, blocks):
        # We can't filter if we don't have enough pages to find common elements
        if len(blocks) < 3:
            return []

        text = [self.clean_text(b.raw_text(document)) for b in blocks]
        counter = Counter(text)
        common = [k for k, v in counter.items() if v > len(blocks) * self.common_element_threshold]
        for b in blocks:
            if self.clean_text(b.raw_text(document)) in common:
                for span in b.contained_blocks(document, [BlockTypes.Span]):
                    span.ignore_for_output = True
