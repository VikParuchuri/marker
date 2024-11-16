from typing import Optional

from pydantic import BaseModel

from marker.v2.builders import BaseBuilder
from marker.v2.schema import BlockTypes
from marker.v2.schema.document import Document
from marker.v2.schema.groups import GROUP_BLOCK_REGISTRY, ListGroup
from marker.v2.schema.groups.page import PageGroup


class StructureBuilder(BaseBuilder):
    gap_threshold: int = 10

    def __init__(self, config: Optional[BaseModel] = None):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            self.group_caption_blocks(page)
            self.group_lists(page)

    def group_caption_blocks(self, page: PageGroup):
        for i, block_id in enumerate(page.structure):
            block = page.get_block(block_id)
            if block.block_type not in [BlockTypes.Table, BlockTypes.Figure, BlockTypes.Picture]:
                continue

            block_structure = [block_id]
            selected_polygons = [block.polygon]
            for j, prev_block_id in enumerate(page.structure[:i][::-1]):
                prev_block = page.get_block(prev_block_id)
                if all([
                    prev_block.block_type in [BlockTypes.Caption, BlockTypes.Footnote],
                    prev_block.polygon.minimum_gap(block.polygon) < self.gap_threshold
                ]):
                    block_structure.insert(0, prev_block_id)
                    selected_polygons.append(prev_block.polygon)
                else:
                    break

            for j, next_block_id in enumerate(page.structure[i + 1:]):
                next_block = page.get_block(next_block_id)
                if all([
                    next_block.block_type in [BlockTypes.Caption, BlockTypes.Footnote],
                    next_block.polygon.minimum_gap(block.polygon) < self.gap_threshold
                ]):
                    block_structure.append(next_block_id)
                    selected_polygons.append(next_block.polygon)
                else:
                    break

            if len(block_structure) > 1:
                # Create a merged block
                new_block_cls = GROUP_BLOCK_REGISTRY[BlockTypes[block.block_type + "Group"]]
                new_polygon = block.polygon.merge(selected_polygons)
                group_block = page.add_block(new_block_cls, new_polygon)
                group_block.structure = block_structure

                # Update the structure of the page to reflect the new block
                page.update_structure_item(block_id, group_block.id)
                page.remove_structure_items(block_structure)

    def group_lists(self, page: PageGroup):
        for i, block_id in enumerate(page.structure):
            block = page.get_block(block_id)
            if block.block_type not in [BlockTypes.ListItem]:
                continue
            block_structure = [block_id]
            selected_polygons = [block.polygon]

            for j, next_block_id in enumerate(page.structure[i + 1:]):
                next_block = page.get_block(next_block_id)
                if all([
                    next_block.block_type == BlockTypes.ListItem,
                    next_block.polygon.minimum_gap(block.polygon) < self.gap_threshold
                ]):
                    block_structure.append(next_block_id)
                    selected_polygons.append(next_block.polygon)
                else:
                    break

            if len(block_structure) > 1:
                new_polygon = block.polygon.merge(selected_polygons)
                group_block = page.add_block(ListGroup, new_polygon)
                group_block.structure = block_structure

                # Update the structure of the page to reflect the new block
                page.update_structure_item(block_id, group_block.id)
                page.remove_structure_items(block_structure)
