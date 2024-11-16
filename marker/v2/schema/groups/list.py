from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class ListGroup(Block):
    block_type: BlockTypes = BlockTypes.ListGroup

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        return f"<ul>{template}</ul>"
