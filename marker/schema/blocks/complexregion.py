from marker.schema import BlockTypes
from marker.schema.blocks import Block


class ComplexRegion(Block):
    block_type: BlockTypes = BlockTypes.ComplexRegion
    markdown: str | None = None

    def assemble_html(self, child_blocks, parent_structure):
        if self.markdown:
            return self.markdown
        else:
            template = super().assemble_html(child_blocks, parent_structure)
            return f"<p>{template}</p>"
