from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Caption(Block):
    block_type: BlockTypes = BlockTypes.Caption
    block_description: str = "A text caption that is directly above or below an image or table. Only used for text describing the image or table.  "
    replace_output_newlines: bool = True

