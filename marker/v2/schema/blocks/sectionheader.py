from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class SectionHeader(Block):
    block_type: BlockTypes = BlockTypes.SectionHeader
    heading_level: int | None = None

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        tag = f"h{self.heading_level}" if self.heading_level else "h2"
        return f"<{tag}>{template}</{tag}>"
