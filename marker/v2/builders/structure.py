from pydantic import BaseModel

from marker.v2.builders import BaseBuilder
from marker.v2.schema.document import Document
from marker.v2.schema.groups import GROUP_BLOCK_REGISTRY


class StructureConfig(BaseModel):
    gap_threshold: int = 10


class StructureBuilder(BaseBuilder):
    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            initial_structure = [block._id for block in page.children]

    def group_caption_blocks(self, page):
        for i, block in enumerate(page.children):
            if block.block_type in ["Table", "Figure", "Picture"]:
                block_structure = [block._id]

                for j, prev_block in enumerate(page.children[:i][::-1]):
                    if all([
                        prev_block.block_type in ["Caption", "Footnote"],
                        prev_block.minimum_gap(block) < self.config.gap_threshold
                    ]):
                        block_structure.append(prev_block._id)
                    else:
                        break

                for j, next_block in enumerate(page.children[i + 1:]):
                    if all([
                        next_block.block_type in ["Caption", "Footnote"],
                        next_block.minimum_gap(block) < self.config.gap_threshold
                    ]):
                        block_structure.append(next_block._id)
                    else:
                        break

                if len(block_structure) > 0:
                    new_block_cls = GROUP_BLOCK_REGISTRY[block.block_type]
                    # TODO: fix the polygon to span all the blocks inside the grouped block
                    # TODO: Add the structure, etc, to the block
                    block = page.add_block(new_block_cls, block.polygon)

        # Table, Figure, Picture
        pass

    def group_lists(self, page):
        pass
