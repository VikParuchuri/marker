from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Footnote(Block):
    block_type: BlockTypes = BlockTypes.Footnote
    replace_output_newlines: bool = True
