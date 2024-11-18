from typing import Dict, List

from PIL import Image

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block, BlockId
from marker.v2.schema.polygon import PolygonBox
from marker.v2.schema.text.line import Line
from marker.v2.schema.text.span import Span


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
        block: Block = self.children[block_id.block_id]
        assert block.block_id == block_id.block_id
        return block

    def merge_blocks(
        self,
        page_lines: List[Line],
        line_spans: Dict[int, List[Span]],
        text_extraction_method: str,
        excluded_block_types=[BlockTypes.Line, BlockTypes.Span]
    ):
        provider_line_idxs = set(range(len(page_lines)))
        max_intersections = {}

        for line_idx, line in enumerate(page_lines):
            for block_idx, block in enumerate(self.children):
                if block.block_type in excluded_block_types:
                    continue
                intersection_pct = line.polygon.intersection_pct(block.polygon)
                if line_idx not in max_intersections:
                    max_intersections[line_idx] = (intersection_pct, block_idx)
                elif intersection_pct > max_intersections[line_idx][0]:
                    max_intersections[line_idx] = (intersection_pct, block_idx)

        assigned_line_idxs = set()
        for line_idx, line in enumerate(page_lines):
            if line_idx in max_intersections and max_intersections[line_idx][0] > 0.0:
                self.add_full_block(line)
                block_idx = max_intersections[line_idx][1]
                block: Block = self.children[block_idx]
                block.add_structure(line)
                block.polygon = block.polygon.merge([line.polygon])
                block.text_extraction_method = text_extraction_method
                assigned_line_idxs.add(line_idx)
                for span in line_spans[line_idx]:
                    self.add_full_block(span)
                    line.add_structure(span)

        for line_idx in provider_line_idxs.difference(assigned_line_idxs):
            min_dist = None
            min_dist_idx = None
            line = page_lines[line_idx]
            for block_idx, block in enumerate(self.children):
                if block.block_type in excluded_block_types:
                    continue
                dist = line.polygon.center_distance(block.polygon)
                if min_dist_idx is None or dist < min_dist:
                    min_dist = dist
                    min_dist_idx = block_idx

            if min_dist_idx is not None:
                self.add_full_block(line)
                nearest_block = self.children[min_dist_idx]
                nearest_block.add_structure(line)
                nearest_block.polygon = nearest_block.polygon.merge([line.polygon])
                nearest_block.text_extraction_method = text_extraction_method
                assigned_line_idxs.add(line_idx)
                for span in line_spans[line_idx]:
                    self.add_full_block(span)
                    line.add_structure(span)
