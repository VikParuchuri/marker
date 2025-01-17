from marker.schema import BlockTypes
from marker.schema.blocks import Block


class PageFooter(Block):
    block_type: str = BlockTypes.PageFooter
    block_description: str = "Text that appears at the bottom of a page, like a page number."

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        template = super().assemble_html(document, child_blocks, parent_structure)
        template = template.replace("\n", " ")
        return f"<p>{template}</p>"
