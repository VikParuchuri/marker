from typing import Annotated

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document
from marker.schema.text import Line
from marker.util import matrix_intersection_area


class LineMergeProcessor(BaseProcessor):
    """
    A processor for merging inline math lines.
    """
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)
    min_merge_pct: Annotated[
        float,
        "The minimum percentage of intersection area to consider merging."
    ] = .02
    min_merge_ydist: Annotated[
        float,
        "The minimum y distance between lines to consider merging."
    ] = 5
    intersection_pct_threshold: Annotated[
        float,
        "The total amount of intersection area concentrated in the max intersection block."
    ] = .9

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if block.structure is None:
                    continue

                if not len(block.structure) >= 2:  # Skip single lines
                    continue

                lines = block.contained_blocks(document, (BlockTypes.Line,))
                line_bboxes = [l.polygon.bbox for l in lines]
                intersections = matrix_intersection_area(line_bboxes, line_bboxes)

                merges = []
                merge = []
                for i in range(len(line_bboxes) - 1):
                    next_idx = i + 1
                    intersection_val = intersections[i, next_idx]
                    intersection_pct = intersection_val / max(1, lines[i].polygon.area)
                    intersection_row = intersections[i]
                    intersection_row[i] = 0 # Zero out the current idx
                    max_intersection_idx = intersection_row.argmax()
                    total_intersection = max(1, sum(intersection_row))
                    max_intersection = intersection_row[max_intersection_idx]


                    if all([
                        max_intersection_idx == next_idx, # The next line is the max intersection line
                        intersection_pct >= self.min_merge_pct,
                        abs(lines[i].polygon.y_start - lines[next_idx].polygon.y_start) <= self.min_merge_ydist,
                        abs(lines[i].polygon.y_end - lines[next_idx].polygon.y_end) <= self.min_merge_ydist,
                        max_intersection / total_intersection >= self.intersection_pct_threshold
                    ]):
                        merge.append(i)
                    else:
                        merges.append(merge)
                        merge = []

                if merge:
                    merges.append(merge)

                merges = [m for m in merges if len(m) > 1]
                merged = set()
                for merge in merges:
                    merge = [m for m in merge if m not in merged]
                    if len(merge) < 2:
                        continue

                    line: Line = lines[merge[0]]
                    merged.add(merge[0])
                    for idx in merge[1:]:
                        other_line: Line = lines[idx]
                        line.merge(other_line)
                        block.structure.remove(other_line.id)
                        merged.add(idx)

                    # It is probably math if we are merging provider lines like this
                    if not line.formats:
                        line.formats = ["math"]
                    elif "math" not in line.formats:
                        line.formats.append("math")
