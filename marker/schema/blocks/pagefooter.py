from marker.schema import BlockTypes
from marker.schema.blocks import Block


class PageFooter(Block):
    block_type: str = BlockTypes.PageFooter
    replace_output_newlines: bool = True
    ignore_for_output: bool = True
