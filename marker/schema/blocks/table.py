from typing import List

from tabled.formats import html_format
from tabled.schema import SpanTableCell

from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Table(Block):
    block_type: BlockTypes = BlockTypes.Table
    cells: List[SpanTableCell] | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        child_ref_blocks = [block for block in child_blocks if block.id.block_type == BlockTypes.Reference]
        template = super().assemble_html(child_ref_blocks, parent_structure)
        if self.cells:
            return template + str(html_format(self.cells))
        return f"<p>{template}</p>"
