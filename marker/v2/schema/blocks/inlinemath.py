from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class InlineMath(Block):
    block_type: BlockTypes = BlockTypes.TextInlineMath
    has_continuation: bool = False

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")

        class_name = "text"
        if self.has_continuation:
            class_name += " _has-continuation"
        return f"<p class='{class_name}'>{template}</p>"
