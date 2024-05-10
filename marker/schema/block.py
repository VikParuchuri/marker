import math
from typing import List, Optional

from pydantic import field_validator
import ftfy

from marker.schema.bbox import BboxElement
from marker.settings import settings


class BlockType(BboxElement):
    block_type: str


class Span(BboxElement):
    text: str
    span_id: str
    font: str
    font_weight: float
    font_size: float
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    image: Optional[bool] = None


    @field_validator('text')
    @classmethod
    def fix_unicode(cls, text: str) -> str:
        return ftfy.fix_text(text)


class Line(BboxElement):
    spans: List[Span]

    @property
    def prelim_text(self):
        return "".join([s.text for s in self.spans])

    @property
    def start(self):
        return self.spans[0].bbox[0]


class Block(BboxElement):
    lines: List[Line]
    pnum: int
    block_type: Optional[str] = None

    @property
    def prelim_text(self):
        return "\n".join([l.prelim_text for l in self.lines])

    def filter_spans(self, bad_span_ids):
        new_lines = []
        for line in self.lines:
            new_spans = []
            for span in line.spans:
                if not span.span_id in bad_span_ids:
                    new_spans.append(span)
            line.spans = new_spans
            if len(new_spans) > 0:
                new_lines.append(line)
        self.lines = new_lines

    def filter_bad_span_types(self):
        new_lines = []
        for line in self.lines:
            new_spans = []
            for span in line.spans:
                if self.block_type not in settings.BAD_SPAN_TYPES:
                    new_spans.append(span)
            line.spans = new_spans
            if len(new_spans) > 0:
                new_lines.append(line)
        self.lines = new_lines

    def get_min_line_start(self):
        line_starts = [line.start for line in self.lines]
        if len(line_starts) == 0:
            return None
        return min(line_starts)


def bbox_from_lines(lines: List[Line]):
    min_x = min([line.bbox[0] for line in lines])
    min_y = min([line.bbox[1] for line in lines])
    max_x = max([line.bbox[2] for line in lines])
    max_y = max([line.bbox[3] for line in lines])
    return [min_x, min_y, max_x, max_y]


def split_block_lines(block: Block, split_line_idx: int):
    new_blocks = []
    if split_line_idx >= len(block.lines):
        return [block]
    elif split_line_idx == 0:
        return [block]
    else:
        new_blocks.append(Block(lines=block.lines[:split_line_idx], bbox=bbox_from_lines(block.lines[:split_line_idx]), pnum=block.pnum))
        new_blocks.append(Block(lines=block.lines[split_line_idx:], bbox=bbox_from_lines(block.lines[split_line_idx:]), pnum=block.pnum))
    return new_blocks


def find_insert_block(blocks: List[Block], bbox):
    nearest_match = None
    match_dist = None
    for idx, block in enumerate(blocks):
        try:
            dist = math.sqrt((block.bbox[1] - bbox[1]) ** 2 + (block.bbox[0] - bbox[0]) ** 2)
        except Exception as e:
            continue

        if nearest_match is None or dist < match_dist:
            nearest_match = idx
            match_dist = dist
    if nearest_match is None:
        return 0
    return nearest_match


