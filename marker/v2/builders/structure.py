from typing import List, Optional

from pydantic import BaseModel

from marker.v2.builders import BaseBuilder
from marker.v2.schema.document import Document
from marker.v2.schema.groups import GROUP_BLOCK_REGISTRY, ListGroup
from marker.v2.schema.groups.page import PageGroup


class StructureBuilder(BaseBuilder):
    gap_threshold: int = 10

    def __init__(self, config: Optional[BaseModel] = None):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            page.structure = [block._id for block in page.children]
            self.group_caption_blocks(page)
            self.group_lists(page)

    def group_caption_blocks(self, page: PageGroup):
        for i, block in enumerate(page.children):
            if block.block_type not in ["Table", "Figure", "Picture"]:
                continue

            block_structure = [block._id]
            selected_polygons = [block.polygon]

            for j, prev_block in enumerate(page.children[:i][::-1]):
                if all([
                    prev_block.block_type in ["Caption", "Footnote"],
                    prev_block.minimum_gap(block) < self.gap_threshold
                ]):
                    block_structure.insert(prev_block._id, 0)
                    selected_polygons.append(prev_block.polygon)
                    page.structure.remove(prev_block._id)
                else:
                    break

            for j, next_block in enumerate(page.children[i + 1:]):
                if all([
                    next_block.block_type in ["Caption", "Footnote"],
                    next_block.minimum_gap(block) < self.gap_threshold
                ]):
                    block_structure.append(next_block._id)
                    selected_polygons.append(next_block.polygon)
                    page.structure.remove(next_block._id)
                else:
                    break

            if len(block_structure) > 1:
                # Create a merged block
                new_block_cls = GROUP_BLOCK_REGISTRY[block.block_type + "Group"]
                new_polygon = block.polygon.merge(selected_polygons)
                group_block = page.add_block(new_block_cls, new_polygon)
                group_block.structure = block_structure

                # Update the structure of the page to reflect the new block
                orig_block_idx = page.structure.index(block_structure[0])
                page.structure[orig_block_idx] = group_block._id

    def group_lists(self, page: PageGroup):
        for i, block in enumerate(page.children):
            if block.block_type not in ["ListItem"]:
                continue
            block_structure = [block._id]
            selected_polygons = [block.polygon]

            for j, next_block in enumerate(page.children[i + 1:]):
                if all([
                    next_block.block_type == "ListItem",
                    next_block.minimum_gap(block) < self.gap_threshold
                ]):
                    block_structure.append(next_block._id)
                    selected_polygons.append(next_block.polygon)
                    page.structure.remove(next_block._id)
                else:
                    break

            if len(block_structure) > 1:
                new_polygon = block.polygon.merge(selected_polygons)
                block = page.add_block(ListGroup, new_polygon)
                block.structure = block_structure
