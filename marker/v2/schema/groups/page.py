from marker.v2.schema import Block
from PIL import Image

from marker.v2.schema.blocks import LAYOUT_BLOCK_REGISTRY
from marker.v2.schema.polygon import PolygonBox


class PageGroup(Block):
    block_type = "Page"
    lowres_image: Image.Image | None = None
    highres_image: Image.Image | None = None

    def add_block(self, block_type: str, polygon: PolygonBox):
        max_id = max([b.block_id for b in self.blocks], default=0)

        block_cls = LAYOUT_BLOCK_REGISTRY[block_type]
        block = block_cls(
            polygon=polygon,
            block_id=max_id + 1,
            page_id=self.block_id,
        )
        if isinstance(self.children, list):
            self.children.append(block)
        else:
            self.children = [block]
