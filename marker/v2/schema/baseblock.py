from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel


class Block(BaseModel):
    pnum: int
    block_type: Optional[str] = None
    block_num: Optional[int] = None
    children: List[Block]
    polygon: List[List[float]]

    @property
    def _id(self):
        return f"/page/{self.pnum}/block/{self.block_num}"

