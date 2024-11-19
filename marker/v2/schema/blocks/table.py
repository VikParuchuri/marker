from typing import List

from tabled.formats import html_format
from tabled.schema import SpanTableCell

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Table(Block):
    block_type: BlockTypes = BlockTypes.Table
    cells: List[SpanTableCell] | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        if self.cells:
            return html_format(self.cells)
        else:
            template = super().assemble_html(child_blocks, parent_structure)
            return f"<p>{template}</p>"
