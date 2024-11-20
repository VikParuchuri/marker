import math
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

                    column_break, page_break = False, False
                    next_block = page.get_next_block(block)
                    if next_block is not None:  # we check for a column break
                        column_break = (
                            next_block.polygon.y_start < block.polygon.y_start and
                            next_block.polygon.x_start > block.polygon.x_start
                        )
                    else:  # It's a page break since we don't have a next block in the page
                        page_break = True

                    if not (column_break or page_break):
                        continue

                    next_block_starts_indented = True
                    next_block_in_first_quadrant = False

                    if column_break:
                        if next_block.block_type not in self.block_types:
                            continue
                        if next_block.structure is None:  # This is odd though, why do we have text blocks with no structure?
                            continue

                        # we check for next_block indentation
                        new_block_lines = [page.get_block(block_id) for block_id in next_block.structure]
                        min_x = math.ceil(min([l.polygon.x_start for l in new_block_lines]))
                        next_block_starts_indented = new_block_lines[0].polygon.x_start > min_x
                    else:  # page break
                        next_page = document.get_next_page(page)
                        if next_page is None:
                            continue  # we're on the last page, so we don't worry about merging

                        # Go through the next page only
                        for next_page_block_id in next_page.structure:
                            if next_page_block_id.block_type in [BlockTypes.PageHeader, BlockTypes.PageFooter]:
                                continue  # skip headers and footers
                            if next_page_block_id.block_type not in self.block_types:
                                break  # we found a non-text block, so we can stop looking

                            # we have our text_block
                            next_page_block = next_page.get_block(next_page_block_id)
                            if next_page_block.structure is None:
                                break  # This is odd though, why do we have text blocks with no structure?

                            # check if the new block is indented
                            new_block_lines = [next_page.get_block(block_id) for block_id in next_page_block.structure]
                            min_x = math.ceil(min([l.polygon.x_start for l in new_block_lines]))
                            next_block_starts_indented = new_block_lines[0].polygon.x_start > min_x

                            next_block_in_first_quadrant = (next_page_block.polygon.x_start < next_page.polygon.width // 2) and \
                                (next_page_block.polygon.y_start < next_page.polygon.height // 2)
                            break
                        else:
                            continue  # we didn't break anywhere so we continue

                    lines: List[Line] = [page.get_block(block_id) for block_id in block.structure]
                    max_x = math.floor(max([l.polygon.x_end for l in lines]))
                    last_line_is_full_width = lines[-1].polygon.x_end >= max_x

                    last_line_is_hyphentated = regex.compile(r'.*[\p{Ll}|\d][-—¬]\s?$', regex.DOTALL).match(lines[-1].raw_text(document).strip())

                    if (last_line_is_full_width or last_line_is_hyphentated) and \
                            not next_block_starts_indented and \
                            ((next_block_in_first_quadrant and page_break) or column_break):
                        block.has_continuation = True
