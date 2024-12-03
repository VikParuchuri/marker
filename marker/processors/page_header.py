from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup


class PageHeaderProcessor(BaseProcessor):
    """
    A processor for moving PageHeaders to the top
    """
    block_types = (BlockTypes.PageHeader,)

    def __call__(self, document: Document):
        for page in document.pages:
            self.move_page_header_to_top(page, document)

    def move_page_header_to_top(self, page: PageGroup, document: Document):
        page_header_blocks = page.contained_blocks(document, self.block_types)
        page_header_block_ids = [block.id for block in page_header_blocks]
        for block_id in page_header_block_ids:
            page.structure.remove(block_id)
        page.structure[:0] = page_header_block_ids

