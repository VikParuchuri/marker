from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Reference(Block):
    block_type: BlockTypes = BlockTypes.Reference
    ref: str

    def assemble_html(self, child_blocks, parent_structure=None):
        template = super().assemble_html(child_blocks, parent_structure)
        return f"<span id='{self.ref}'>{template}</span>"
