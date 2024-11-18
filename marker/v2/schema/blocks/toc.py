from typing import List

from tabled.formats import html_format
from tabled.schema import SpanTableCell

from marker.v2.schema.blocks import Block


class TableOfContents(Block):
    block_type: str = "TableOfContents"
    cells: List[SpanTableCell] | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        return html_format(self.cells)
