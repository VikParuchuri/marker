from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Footnote(Block):
    block_type: BlockTypes = BlockTypes.Footnote
    block_description: str = "A footnote that explains a term or concept in the document."

    def assemble_html(self, document, child_blocks, parent_structure):
        template = super().assemble_html(document, child_blocks, parent_structure)
        template = template.replace("\n", " ")

        return f"<p>{template}</p>"
