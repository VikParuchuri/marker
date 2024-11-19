import html

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Equation(Block):
    block_type: BlockTypes = BlockTypes.Equation
    latex: str | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        if self.latex:
            return f"<p><math>{html.escape(self.latex)}</math></p>"
        else:
            template = super().assemble_html(child_blocks, parent_structure)
            return f"<p>{template}</p>"
