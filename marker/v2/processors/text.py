from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document
from marker.v2.schema.text.line import Line
from typing import List


class TextProcessor(BaseProcessor):
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.children:
                if block.block_type in self.block_types:
                    if not len(block.structure) > 3:  # Skip non paragraphs
                        continue

                    block_idx = page.structure.index(block.id)
                    if block_idx + 1 < len(page.structure):
                        next_block = page.structure[block_idx + 1]
                        if next_block.block_type not in self.block_types:
                            continue

                    lines: List[Line] = [page.get_block(block_id) for block_id in block.structure]
                    avg_width = sum([l.polygon.width for l in lines]) / len(lines)

                    if (lines[-1].polygon.width - avg_width) > 0:
                        block.has_continuation = True
