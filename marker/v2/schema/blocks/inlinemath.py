from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class InlineMath(Block):
    block_type: BlockTypes = BlockTypes.TextInlineMath
    has_continuation: bool = False
    is_continuation: bool = False

    def assemble_html(self, child_blocks, parent_structure):
        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")

        if not self.is_continuation:
            template = f"<p>{template}"
        if not self.has_continuation:
            template = f"{template}</p>"
        return template
