from marker.v2.schema.blocks import Block


class Text(Block):
    block_type: str = "Text"

    def assemble_html(self, child_blocks):
        template = super().assemble_html(child_blocks)
        return f"<p>{template}</p>"
