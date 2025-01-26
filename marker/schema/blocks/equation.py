import html

from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Equation(Block):
    block_type: BlockTypes = BlockTypes.Equation
    html: str | None = None
    block_description: str = "A block math equation."

    def assemble_html(self, document, child_blocks, parent_structure=None):
        if self.html:
            child_ref_blocks = [block for block in child_blocks if block.id.block_type == BlockTypes.Reference]
            html_out = super().assemble_html(document, child_ref_blocks, parent_structure)
            html_out += f"""<p block-type='{self.block_type}'>{self.html}</p>"""
            return html_out
        else:
            template = super().assemble_html(document, child_blocks, parent_structure)
            return f"<p block-type='{self.block_type}'>{template}</p>"
