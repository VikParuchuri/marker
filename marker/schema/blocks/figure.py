from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Figure(Block):
    block_type: BlockTypes = BlockTypes.Figure

    def assemble_html(self, child_blocks, parent_structure):
        return f"<p>Image {self.id}</p>"
