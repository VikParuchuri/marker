from collections import Counter
from typing import List, Optional

from pydantic import BaseModel

from marker.schema.bbox import BboxElement


class MergedLine(BboxElement):
    text: str
    fonts: List[str]

    def most_common_font(self):
        counter = Counter(self.fonts)
        return counter.most_common(1)[0][0]


class MergedBlock(BboxElement):
    lines: List[MergedLine]
    pnum: int
    block_type: Optional[str]


class FullyMergedBlock(BaseModel):
    text: str
    block_type: str
