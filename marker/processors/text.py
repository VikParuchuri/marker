import math
from typing import List

import regex

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.text.line import Line


class TextProcessor(BaseProcessor):
    """
    A processor for merging text across pages and columns.

    Attributes:
        column_gap_ratio (float):
            The minimum ratio of the page width to the column gap to consider a column break.
            Default is 0.02.
    """
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)
    column_gap_ratio = 0.02  # column gaps are atleast 2% of the current column width

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if block.structure is None:
                    continue

                if not len(block.structure) >= 2:  # Skip single lines
                    continue
                
                column_gap = block.polygon.width * self.column_gap_ratio

                column_break, page_break = False, False
                next_block = page.get_next_block(block)

                if  next_block is not None: # next block exists
                    # we check for a column break
                    column_break = (
                        math.floor(next_block.polygon.y_start) <= math.floor(block.polygon.y_start) and
                        next_block.polygon.x_start > (block.polygon.x_end + column_gap)
                    )
                else:  # It's a page break since we don't have a next block in the page
                    page_break = True

                if not (column_break or page_break):
                    continue

                next_block_starts_indented = True
                next_block_in_first_quadrant = False
                last_line_is_full_width = False
                last_line_is_hyphentated = False
                new_block_lines = []

                if column_break:
                    if next_block.block_type not in self.block_types:
                        continue
                    if next_block.structure is None:  # This is odd though, why do we have text blocks with no structure?
                        continue

                    new_block_lines = next_block.structure_blocks(document)
                else:  # page break
                    next_page = document.get_next_page(page)
                    if next_page is None:
                        continue  # we're on the last page, so we don't worry about merging

                    # Go through the next page only
                    for next_page_block_id in next_page.structure:
                        if next_page_block_id.block_type in [BlockTypes.PageHeader, BlockTypes.PageFooter]:
                            continue  # skip headers and footers

                        # we have our block
                        next_page_block = next_page.get_block(next_page_block_id)
                        if next_page_block.ignore_for_output:
                            continue # skip ignored blocks

                        if not (next_page_block.structure is not None and \
                            next_page_block.block_type in self.block_types): 
                            # we found a non-text block or an empty text block, so we can stop looking
                            break

                        new_block_lines = next_page_block.structure_blocks(document)

                        next_block_in_first_quadrant = (next_page_block.polygon.x_start < next_page.polygon.width // 2) and \
                            (next_page_block.polygon.y_start < next_page.polygon.height // 2)
                        break
                    else:
                        continue  # we didn't break anywhere so we continue

                # we check for next_block indentation
                if len(new_block_lines):
                    min_x = math.ceil(min([l.polygon.x_start for l in new_block_lines]))
                    next_block_starts_indented = new_block_lines[0].polygon.x_start > min_x

                lines: List[Line] = [l for l in block.structure_blocks(document) if l.polygon.width > 1]
                if len(lines):
                    max_x = math.floor(max([l.polygon.x_end for l in lines]))
                    last_line_is_full_width = lines[-1].polygon.x_end >= max_x

                    last_line_is_hyphentated = regex.compile(r'.*[\p{Ll}|\d][-—¬]\s?$', regex.DOTALL).match(lines[-1].raw_text(document).strip())

                if (last_line_is_full_width or last_line_is_hyphentated) and \
                        not next_block_starts_indented and \
                        ((next_block_in_first_quadrant and page_break) or column_break):
                    block.has_continuation = True
