from marker.v2.schema.blocks import Block


class ListItem(Block):
    block_type: str = "ListItem"

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        return f"<li>{template}</li>"
