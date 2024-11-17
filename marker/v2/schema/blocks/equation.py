from marker.v2.schema.blocks import Block


class Equation(Block):
    block_type: str = "Equation"
    latex: str | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        return f"<div class='math'>{self.latex}</div>"
