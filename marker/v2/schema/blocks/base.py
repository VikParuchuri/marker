from __future__ import annotations

from typing import Optional, List, Any

from pydantic import BaseModel, ConfigDict, field_validator

from marker.v2.schema.polygon import PolygonBox


class BlockOutput(BaseModel):
    html: str
    polygon: PolygonBox
    id: BlockId
    children: List[BlockOutput] | None = None


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
        if not isinstance(other, (BlockId, str)):
            return NotImplemented

        if isinstance(other, str):
            return str(self) == other
        else:
            return self.page_id == other.page_id and self.block_id == other.block_id and self.block_type == other.block_type

    @field_validator("block_type")
    @classmethod
    def validate_block_type(cls, v):
        from marker.v2.schema import BlockTypes
        if not hasattr(BlockTypes, v):
            raise ValueError(f"Invalid block type: {v}")
        return v


class Block(BaseModel):
    polygon: PolygonBox
    block_type: Optional[str] = None
    block_id: Optional[int] = None
    page_id: Optional[int] = None
    structure: List[BlockId] | None = None  # The top-level page structure, which is the block ids in order
    rendered: Any | None = None # The rendered output of the block
    text_extraction_method: str = "pdftext"

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @property
    def id(self) -> BlockId:
        return BlockId(
            page_id=self.page_id,
            block_id=self.block_id,
            block_type=self.block_type
        )

    def add_structure(self, block: Block):
        self.polygon = self.polygon.merge([block.polygon])

        if self.structure is None:
            self.structure = [block.id]
        else:
            self.structure.append(block.id)

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

    def assemble_html(self, child_blocks, parent_structure=None):
        template = ""
        for c in child_blocks:
            template += f"<content-ref src='{c.id}'></content-ref>"
        return template

    def render(self, document, parent_structure):
        child_content = []
        if self.structure is not None and len(self.structure) > 0:
            for block_id in self.structure:
                block = document.get_block(block_id)
                child_content.append(block.render(document, self.structure))

        return BlockOutput(
            html=self.assemble_html(child_content, parent_structure),
            polygon=self.polygon,
            id=self.id,
            children=child_content
        )
