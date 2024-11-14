from marker.v2.schema.blocks import Block


class Equation(Block):
    block_type: str = "Equation"
    latex: str | None = None
