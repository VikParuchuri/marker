from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from marker.v2.schema import PolygonBox


class Block(BaseModel):
    polygon: PolygonBox
    block_type: Optional[str] = None
    block_id: Optional[int] = None
    page_id: Optional[int] = None
    structure: List[str] | None = None  # The top-level page structure, which is the block ids in order

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _id(self):
        page_path = f"/page/{self.page_id}"
        if self.block_id is not None:
            return f"{page_path}/{self.block_type}/{self.block_id}"
        else:
            return page_path

    def add_structure(self, block: Block):
        self.polygon = self.polygon.merge([block.polygon])

        if self.structure is None:
            self.structure = [block._id]
        else:
            self.structure.append(block._id)

    def raw_text(self, document) -> str:
        from marker.v2.schema.text.line import Line
        from marker.v2.schema.text.span import Span

        if self.structure is None:
            return ""

        text = ""
        for block_id in self.structure:
            block = document.get_block(block_id)
            if isinstance(block, Span):
                text += block.text
            else:
                text += block.raw_text(document)
                if isinstance(block, Line):
                    text += "\n"
        return text
