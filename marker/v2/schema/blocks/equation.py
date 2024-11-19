import html

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Equation(Block):
    block_type: BlockTypes = BlockTypes.Equation
    latex: str | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        return f"<p><math>{html.escape(self.latex)}</math></p>"
