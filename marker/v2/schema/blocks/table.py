from typing import List

from tabled.schema import SpanTableCell

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block


class Table(Block):
    block_type: BlockTypes = BlockTypes.Table
    cells: List[SpanTableCell] | None = None
