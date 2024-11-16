from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Equation(Block):
    block_type: BlockTypes = BlockTypes.Equation
    latex: str | None = None
