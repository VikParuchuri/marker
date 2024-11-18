from marker.v2.schema.blocks import Block


class Figure(Block):
    block_type: str = "Figure"

    def assemble_html(self, child_blocks, parent_structure):
        return f"<p>Image {self.block_id}</p>"
