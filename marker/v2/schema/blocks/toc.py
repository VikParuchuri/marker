from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class TableOfContents(Block):
    block_type: BlockTypes = BlockTypes.TableOfContents
