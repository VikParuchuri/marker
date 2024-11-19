from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class InlineMath(Block):
    block_type: BlockTypes = BlockTypes.TextInlineMath
    has_continuation: bool = False

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")

        class_attr = ""
        if self.has_continuation:
            class_attr = " class='has-continuation'"
        return f"<p {class_attr}>{template}</p>"
