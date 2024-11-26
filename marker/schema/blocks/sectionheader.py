from marker.schema import BlockTypes
from marker.schema.blocks import Block


class SectionHeader(Block):
    block_type: BlockTypes = BlockTypes.SectionHeader
    heading_level: int | None = None

    def assemble_html(self, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        tag = f"h{self.heading_level}" if self.heading_level else "h2"
        return f"<{tag}>{template}</{tag}>"
