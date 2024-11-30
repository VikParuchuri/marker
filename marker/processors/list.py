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

                block.has_continuation = True
