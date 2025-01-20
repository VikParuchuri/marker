from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Footnote(Block):
    block_type: BlockTypes = BlockTypes.Footnote
    block_description: str = "A footnote that explains a term or concept in the document."
    replace_output_newlines: bool = True
