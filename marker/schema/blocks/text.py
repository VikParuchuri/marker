from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Text(Block):
    block_type: BlockTypes = BlockTypes.Text
    has_continuation: bool = False
    blockquote: bool = False
    blockquote_level: int = 0

    def assemble_html(self, child_blocks, parent_structure):
        if self.ignore_for_output:
            return ""

        template = super().assemble_html(child_blocks, parent_structure)
        template = template.replace("\n", " ")

        el_attr = f" block-type='{self.block_type}'"
        if self.has_continuation:
            el_attr += " class='has-continuation'"

        if self.blockquote:
            blockquote_prefix = "<blockquote>" * self.blockquote_level
            blockquote_suffix = "</blockquote>" * self.blockquote_level
            return f"{blockquote_prefix}<p{el_attr}>{template}</p>{blockquote_suffix}"
        else:
            return f"<p{el_attr}>{template}</p>"
