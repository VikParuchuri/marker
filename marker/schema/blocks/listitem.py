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
        bullet_pattern = r"(^|[\n ]|<[^>]*>)[•●○■▪▫–—-]( )"
        first_block.html = re.sub(bullet_pattern, r"\1\2", first_block.html)


class ListItem(Block):
    block_type: BlockTypes = BlockTypes.ListItem
    list_indent: bool = False
    list_indent_level: int = 0

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        # Remove the first bullet character
        replace_bullets(child_blocks)

        if self.list_indent:
            ul_prefix = "<ul>" * self.list_indent_level
            ul_suffix = "</ul>" * self.list_indent_level
            return f"{ul_prefix}<li>{template}</li>{ul_suffix}"
        else:
            return f"<li>{template}</li>"
