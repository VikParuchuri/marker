from marker.schema import BlockTypes
from marker.schema.groups.base import Group


class ListGroup(Group):
    block_type: BlockTypes = BlockTypes.ListGroup
    has_continuation: bool = False

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)

        class_attr = f" block-type='{self.block_type}'"
        if self.has_continuation:
            class_attr += " class='has-continuation'"
        return f"<p{class_attr}><ul>{template}</ul></p>"
