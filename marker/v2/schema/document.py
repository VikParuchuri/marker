from __future__ import annotations

from typing import List

from pydantic import BaseModel

from marker.v2.schema.blocks import BlockId
from marker.v2.schema.groups.page import PageGroup
from marker.v2.renderers.util import renderer_for_block


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

    def render(self, renderer_lst: list | None = None):
        if renderer_lst is None:
            renderer_lst = []

        for page in self.pages:
            page.render(self, renderer_lst)

        doc_renderer = renderer_for_block(self, renderer_lst)
        return doc_renderer(self, self, self.pages)
