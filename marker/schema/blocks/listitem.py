import re

from marker.schema import BlockTypes
from marker.schema.blocks import Block


def replace_bullets(child_blocks):
    # Replace bullet characters with a -
    first_block = None
    while len(child_blocks) > 0:
        first_block = child_blocks[0]
        child_blocks = first_block.children

    if first_block is not None and first_block.id.block_type == BlockTypes.Line:
        bullet_pattern = r"(^|[\n ]|<[^>]*>)[•●○ഠ ം◦■▪▫–—-]( )"
        first_block.html = re.sub(bullet_pattern, r"\1\2", first_block.html)


class ListItem(Block):
    block_type: BlockTypes = BlockTypes.ListItem
    list_indent_level: int = 0

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        # Remove the first bullet character
        replace_bullets(child_blocks)

        el_attr = f" block-type='{self.block_type}'"
        if self.list_indent_level:
            return f"<ul><li{el_attr} class='list-indent-{self.list_indent_level}'>{template}</li></ul>"
        return f"<li{el_attr}>{template}</li>"
