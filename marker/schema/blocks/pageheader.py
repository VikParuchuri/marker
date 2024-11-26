from marker.schema import BlockTypes
from marker.schema.blocks import Block


class PageHeader(Block):
    block_type: str = BlockTypes.PageHeader

    def assemble_html(self, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")
        return f"<p>{template}</p>"
