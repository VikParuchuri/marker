from __future__ import annotations

from typing import Optional, List

from pydantic import BaseModel, ConfigDict

from marker.v2.schema import PolygonBox
from marker.v2.schema.blocks.caption import Caption
from marker.v2.schema.blocks.code import Code
from marker.v2.schema.blocks.figure import Figure
from marker.v2.schema.blocks.footnote import Footnote
from marker.v2.schema.blocks.form import Form
from marker.v2.schema.blocks.equation import Equation
from marker.v2.schema.blocks.handwriting import Handwriting
from marker.v2.schema.blocks.inlinemath import InlineMath
from marker.v2.schema.blocks.listitem import ListItem
from marker.v2.schema.blocks.pagefooter import PageFooter
from marker.v2.schema.blocks.pageheader import PageHeader
from marker.v2.schema.blocks.picture import Picture
from marker.v2.schema.blocks.sectionheader import SectionHeader
from marker.v2.schema.blocks.table import Table
from marker.v2.schema.blocks.text import Text
from marker.v2.schema.blocks.toc import TableOfContents
from marker.v2.schema.document import Document
from marker.v2.schema.text.line import Line
from marker.v2.schema.text.span import Span


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
        if self.structure is None:
            self.structure = [block._id]
        else:
            self.structure.append(block._id)

    def raw_text(self, document: Document):
        if self.structure is None:
            return 0

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



LAYOUT_BLOCK_REGISTRY = {
    v.model_fields['block_type'].default: v for k, v in locals().items()
    if isinstance(v, type)
    and issubclass(v, Block)
    and v != Block  # Exclude the base Block class
    and not v.model_fields['block_type'].default.endswith("Group")
}
