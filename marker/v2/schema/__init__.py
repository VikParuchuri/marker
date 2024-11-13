from __future__ import annotations
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

from marker.v2.schema.polygon import PolygonBox


class Block(BaseModel):
    polygon: PolygonBox
    block_type: Optional[str] = None
    block_id: Optional[int] = None
    page_id: Optional[int] = None
    structure: List[str] | None = None  # The top-level page structure, which is the block ids in order

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _id(self):
        page_path = f"/page/{self.pnum}"
        if self.block_num is not None:
            return f"{page_path}/block/{self.block_num}"
        else:
            return page_path
