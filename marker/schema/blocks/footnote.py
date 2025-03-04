from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Footnote(Block):
    block_type: BlockTypes = BlockTypes.Footnote
    block_description: str = "A footnote that explains a term or concept in the document."
    replace_output_newlines: bool = True
    html: str | None = None

    def assemble_html(self, document, child_blocks, parent_structure):
        if self.html:
            return super().handle_html_output(document, child_blocks, parent_structure)

        return super().assemble_html(document, child_blocks, parent_structure)
