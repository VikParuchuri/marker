import re

from marker.schema import BlockTypes
from marker.schema.blocks import Block


def superscript(child_blocks):
    # Superscript leading symbol or digit sequence
    first_block = None
    while len(child_blocks) > 0:
        first_block = child_blocks[0]
        child_blocks = first_block.children

    if first_block is not None and first_block.id.block_type == BlockTypes.Line:
        digit_start = r"^([0-9\W]+)(.*)"
        first_block.html = re.sub(digit_start, r"<sup>\1</sup>\2", first_block.html.lstrip())


class Footnote(Block):
    block_type: BlockTypes = BlockTypes.Footnote

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")

        # Add superscripts to start
        superscript(child_blocks)
        return f"<p>{template}</p>"
