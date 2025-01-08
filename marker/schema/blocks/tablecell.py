from marker.schema import BlockTypes
from marker.schema.blocks import Block


class TableCell(Block):
    block_type: BlockTypes = BlockTypes.TableCell
    rowspan: int
    colspan: int
    row_id: int
    col_id: int
    is_header: bool
    text: str = ""

    def assemble_html(self, document, child_blocks, parent_structure=None):
        tag = "th" if self.is_header else "td"
        return f"<{tag} rowspan={self.rowspan} colspan={self.colspan}>{self.text}</{tag}>"
