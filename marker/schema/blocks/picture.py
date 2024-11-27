from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Picture(Block):
    block_type: BlockTypes = BlockTypes.Picture

    def assemble_html(self, child_blocks, parent_structure):
        return f"<p>Image {self.id}</p>"
