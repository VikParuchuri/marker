from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Figure(Block):
    block_type: BlockTypes = BlockTypes.Figure
    description: str | None = None
    block_description: str = "A chart or other image that contains data."

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.description:
            return f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
        else:
            return ""
