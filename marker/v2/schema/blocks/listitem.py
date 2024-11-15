import re

from marker.v2.schema.blocks import Block


def replace_bullets(text):
    # Replace bullet characters with a -
    bullet_pattern = r"(^|[\n ])[•●○■▪▫–—]( )"
    replaced_string = re.sub(bullet_pattern, r"\1-\2", text)
    return replaced_string

class ListItem(Block):
    block_type: str = "ListItem"

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        template = replace_bullets(template)
        return f"<li>{template}</li>"
