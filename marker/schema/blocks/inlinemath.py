from marker.schema import BlockTypes
from marker.schema.blocks import Block


class InlineMath(Block):
    block_type: BlockTypes = BlockTypes.TextInlineMath
    has_continuation: bool = False

    def assemble_html(self, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")

        class_attr = ""
        if self.has_continuation:
            class_attr = " class='has-continuation'"
        return f"<p{class_attr}>{template}</p>"
