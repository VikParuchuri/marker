from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Handwriting(Block):
    block_type: BlockTypes = BlockTypes.Handwriting
    block_description: str = "A region that contains handwriting."
    html: str | None = None

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.html:
            return self.html
        else:
            template = super().assemble_html(document, child_blocks, parent_structure)
            template = template.replace("\n", " ")
            return f"<p>{template}</p>"
