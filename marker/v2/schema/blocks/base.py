from __future__ import annotations

from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict

from marker.v2.renderers.util import renderer_for_block
from marker.v2.schema.polygon import PolygonBox


class BlockId(BaseModel):
    page_id: int
    block_id: int | None = None
    block_type: str | None = None

    def __str__(self):
        if self.block_type is None or self.block_id is None:
            return f"/page/{self.page_id}"
        return f"/page/{self.page_id}/{self.block_type}/{self.block_id}"

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if not isinstance(other, BlockId):
            return NotImplemented
        return self.page_id == other.page_id and self.block_id == other.block_id and self.block_type == other.block_type


class Block(BaseModel):
    polygon: PolygonBox
    block_type: Optional[str] = None
    block_id: Optional[int] = None
    page_id: Optional[int] = None
    structure: List[BlockId] | None = None  # The top-level page structure, which is the block ids in order
    rendered: Any | None = None # The rendered output of the block

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def _id(self) -> BlockId:
        return BlockId(
            page_id=self.page_id,
            block_id=self.block_id,
            block_type=self.block_type
        )

    def add_structure(self, block: Block):
        self.polygon = self.polygon.merge([block.polygon])

        if self.structure is None:
            self.structure = [block._id]
        else:
            self.structure.append(block._id)

    def update_structure_item(self, old_id: BlockId, new_id: BlockId):
        if self.structure is not None:
            for i, item in enumerate(self.structure):
                if item == old_id:
                    self.structure[i] = new_id
                    break

    def remove_structure_items(self, block_ids: List[BlockId]):
        if self.structure is not None:
            self.structure = [item for item in self.structure if item not in block_ids]

    def raw_text(self, document) -> str:
        from marker.v2.schema.text.line import Line
        from marker.v2.schema.text.span import Span

        if self.structure is None:
            if isinstance(self, Span):
                return self.text
            else:
                return ""

        text = ""
        for block_id in self.structure:
            block = document.get_block(block_id)
            text += block.raw_text(document)
            if isinstance(block, Line):
                text += "\n"
        return text

    def render(self, document, renderer_list: list):
        child_blocks = []
        if self.structure is not None and len(self.structure) > 0:
            for block_id in self.structure:
                block = document.get_block(block_id)
                if not block.rendered:
                    block.render(document, renderer_list)
                child_blocks.append(block)

        renderer = renderer_for_block(self, renderer_list)
        self.rendered = renderer(document, self, child_blocks)
