from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Code(Block):
    block_type: BlockTypes = BlockTypes.Code

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        return f"<pre>{template}</pre>"
