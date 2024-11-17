from marker.v2.schema.blocks import Block


class Picture(Block):
    block_type: str = "Picture"

    def assemble_html(self, child_blocks, parent_structure):
        return f"Image {self.block_id}"
