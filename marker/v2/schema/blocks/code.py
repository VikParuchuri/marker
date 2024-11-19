from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Code(Block):
    block_type: BlockTypes = BlockTypes.Code

    def assemble_html(self, child_blocks, parent_structure):
        template = ""
        for c in child_blocks:
            template += f"<content-ref src='{c.id}'></content-ref>\n"
        return f"<pre>{template}</pre>"
