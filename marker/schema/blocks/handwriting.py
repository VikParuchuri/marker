from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Handwriting(Block):
    block_type: BlockTypes = BlockTypes.Handwriting
    replace_output_newlines: bool = True
