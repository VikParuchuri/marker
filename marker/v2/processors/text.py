from typing import List

import regex

from marker.v2.processors import BaseProcessor
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document
from marker.v2.schema.text.line import Line


class TextProcessor(BaseProcessor):
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.children:
                if block.block_type in self.block_types:
                    if block.structure is None:
                        continue

                    if not len(block.structure) >= 2:  # Skip single lines
                        continue

                    column_or_page_break = False
                    next_block = page.get_next_block(block)
                    if next_block is not None:  # we check for a column break
                        column_or_page_break = (
                            next_block.polygon.y_start < block.polygon.y_start and
                            next_block.polygon.x_start > block.polygon.x_start
                        )
                    else:  # It's a page break since we don't have a next block in the page
                        column_or_page_break = True

                    if not column_or_page_break:
                        continue

                    next_block_starts_indented = True
                    next_block_doc = document.get_next_block(block)
                    if next_block_doc:
                        if next_block_doc.block_type not in self.block_types:
                            continue
                        new_page = document.get_page(next_block_doc.page_id)  # the next block can come from the next page
                        new_block_lines = [new_page.get_block(block_id) for block_id in next_block_doc.structure]
                        min_x = min([l.polygon.x_start for l in new_block_lines])
                        next_block_starts_indented = new_block_lines[0].polygon.x_start > min_x

                    lines: List[Line] = [page.get_block(block_id) for block_id in block.structure]
                    max_x = max([l.polygon.x_end for l in lines])

                    last_line_is_full_width = lines[-1].polygon.x_end >= max_x
                    last_line_is_hyphentated = regex.compile(r'.*[\p{Ll}|\d][-—¬]\s?$', regex.DOTALL).match(lines[-1].raw_text(document).strip())

                    if (last_line_is_full_width or last_line_is_hyphentated) and not next_block_starts_indented:
                        block.has_continuation = True
