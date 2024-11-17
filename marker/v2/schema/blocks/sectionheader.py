from marker.v2.schema.blocks import Block


class SectionHeader(Block):
    block_type: str = "SectionHeader"

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        return f"<h2>{template}</h2>"
