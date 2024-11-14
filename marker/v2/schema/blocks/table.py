from typing import List

from tabled.schema import SpanTableCell

from marker.v2.schema.blocks import Block


class Table(Block):
    block_type: str = "Table"
    cells: List[SpanTableCell] | None = None