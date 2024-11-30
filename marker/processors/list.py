import math

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class ListProcessor(BaseProcessor):
    """
    A processor for merging lists across pages and columns
    """
    block_types = (BlockTypes.ListGroup,)
    ignored_block_types = (BlockTypes.PageHeader, BlockTypes.PageFooter)

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                next_block = document.get_next_block(block, self.ignored_block_types)
                if next_block is None:
                    continue
                if next_block.block_type not in self.block_types:
                    continue
                if next_block.structure is None:
                    continue
                if next_block.ignore_for_output:
                    continue

                column_break, page_break = False, False
                next_block_in_first_quadrant = False

                if next_block.page_id == block.page_id: # block on the same page
                    # we check for a column break
                    column_break = next_block.polygon.y_start <= block.polygon.y_end
                else:
                    page_break = True
                    next_page = document.get_page(next_block.page_id)
                    next_block_in_first_quadrant = (next_block.polygon.x_start < next_page.polygon.width // 2) and \
                                        (next_block.polygon.y_start < next_page.polygon.height // 2)
    
                block.has_continuation = column_break or (page_break and next_block_in_first_quadrant)
