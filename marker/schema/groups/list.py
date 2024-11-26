from marker.schema import BlockTypes
from marker.schema.groups.base import Group


class ListGroup(Group):
    block_type: BlockTypes = BlockTypes.ListGroup

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        return f"<p><ul>{template}</ul></p>"
