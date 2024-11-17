from typing import List

from PIL import Image

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block, BlockId
from marker.v2.schema.polygon import PolygonBox


class PageGroup(Block):
    block_type: BlockTypes = BlockTypes.Page
    lowres_image: Image.Image | None = None
    highres_image: Image.Image | None = None
    children: List[Block] | None = None

    def incr_block_id(self):
        if self.block_id is None:
            self.block_id = 0
        else:
            self.block_id += 1

    def add_child(self, block: Block):
        if self.children is None:
            self.children = [block]
        else:
            self.children.append(block)

    def add_block(self, block_cls: type[Block], polygon: PolygonBox) -> Block:
        self.incr_block_id()
        block = block_cls(
            polygon=polygon,
            block_id=self.block_id,
            page_id=self.page_id,
        )
        self.add_child(block)
        return block

    def add_full_block(self, block: Block) -> Block:
        self.incr_block_id()
        block.block_id = self.block_id
        self.add_child(block)
        return block

    def get_block(self, block_id: BlockId) -> Block | None:
        return self.children[block_id.block_id]
