from typing import List

from pydantic import BaseModel

from marker.v2.schema.blocks import BlockId
from marker.v2.schema.groups.page import PageGroup


class Document(BaseModel):
    filepath: str
    pages: List[PageGroup]

    def get_block(self, block_id: BlockId):
        for page in self.pages:
            block = page.get_block(block_id)
            if block:
                return block
        return None