from typing import List

from tabled.formats import html_format
from tabled.schema import SpanTableCell

from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Table(Block):
    block_type: BlockTypes = BlockTypes.Table
    cells: List[SpanTableCell] | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        if self.cells:
            return str(html_format(self.cells))
        else:
            template = super().assemble_html(child_blocks, parent_structure)
            return f"<p>{template}</p>"
