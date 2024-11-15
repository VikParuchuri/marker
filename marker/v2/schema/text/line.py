from typing import List

from marker.v2.schema.blocks import Block
from marker.v2.schema.text.span import Span


class Line(Block):
    block_type: str = "Line"

    def is_continuation(self, other):
        pass
