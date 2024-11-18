from marker.v2.schema.blocks import Block


class PageHeader(Block):
    block_type: str = "PageHeader"

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        return f"<p>{template}</p>"
