from __future__ import annotations

from typing import List

from pydantic import BaseModel

from marker.v2.schema.blocks import BlockId, BlockOutput
from marker.v2.schema.groups.page import PageGroup


class DocumentOutput(BaseModel):
    children: List[BlockOutput]
    html: str
    block_type: str = "Document"


class Document(BaseModel):
    filepath: str
    pages: List[PageGroup]
    block_type: str = "Document"

    def get_block(self, block_id: BlockId):
        for page in self.pages:
            block = page.get_block(block_id)
            if block:
                return block
        return None

    def assemble_html(self, child_blocks):
        template = ""
        for c in child_blocks:
            template += f"<content-ref src='{c.id}'></content-ref>"
        return template

    def render(self):
        child_content = []
        for page in self.pages:
            child_content.append(page.render(self))

        return DocumentOutput(
            children=child_content,
            html=self.assemble_html(child_content)
        )
