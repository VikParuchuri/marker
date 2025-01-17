from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Caption(Block):
    block_type: BlockTypes = BlockTypes.Caption
    replace_output_newlines: bool = True
