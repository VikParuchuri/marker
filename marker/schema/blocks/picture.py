from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Picture(Block):
    block_type: BlockTypes = BlockTypes.Picture
    description: str | None = None
    block_description: str = "An image block that represents a picture."

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.description:
            return f"<p role='img' data-original-image-id='{self.id}'>Image {self.id} description: {self.description}</p>"
        else:
            return ""
