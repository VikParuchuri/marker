from collections import defaultdict
from copy import deepcopy
from itertools import chain
from typing import List

import numpy as np

from marker.providers import ProviderOutput
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.util import matrix_intersection_area


def merge_provider_lines_detected_lines(
    provider_lines: List[ProviderOutput],
    text_lines: List[PolygonBox],
    image_size,
    page_size,
    page_id,
    provider_line_detected_line_min_overlap_pct: float = 0.1,
    line_vertical_merge_threshold: float = 8,
):
    # When provider lines is empty or no lines detected, return provider lines
    if not provider_lines or not text_lines:
        return provider_lines

    out_provider_lines = []
    horizontal_provider_lines = []
    for j, provider_line in enumerate(provider_lines):
        # Multiply to account for small blocks inside equations, but filter out big vertical lines
        if provider_line.line.polygon.height < provider_line.line.polygon.width * 5:
            horizontal_provider_lines.append((j, provider_line))
        else:
            out_provider_lines.append((j, provider_line))

    provider_line_boxes = [p.line.polygon.bbox for _, p in horizontal_provider_lines]
    detected_line_boxes = [
        PolygonBox(polygon=line.polygon).rescale(image_size, page_size).bbox
        for line in text_lines
    ]

    overlaps = matrix_intersection_area(provider_line_boxes, detected_line_boxes)

    # Find potential merges
    merge_lines = defaultdict(list)
    for i in range(len(provider_line_boxes)):
        max_overlap_pct = np.max(overlaps[i]) / max(
            1, horizontal_provider_lines[i][1].line.polygon.area
        )
        if max_overlap_pct <= provider_line_detected_line_min_overlap_pct:
            continue

        best_overlap = np.argmax(overlaps[i])
        merge_lines[best_overlap].append(i)

    # Filter to get rid of detected lines that include multiple provider lines
    filtered_merge_lines = defaultdict(list)
    for line_idx in merge_lines:
        merge_segment = []
        prev_line = None
        for ml in merge_lines[line_idx]:
            line = horizontal_provider_lines[ml][1].line.polygon
            if prev_line:
                close = (
                    abs(line.y_start - prev_line.y_start)
                    < line_vertical_merge_threshold
                    or abs(line.y_end - prev_line.y_end) < line_vertical_merge_threshold
                )
            else:
                # First line
                close = True

            prev_line = line
            if close:
                merge_segment.append(ml)
            else:
                if merge_segment:
                    filtered_merge_lines[line_idx].append(merge_segment)
                merge_segment = [ml]
        if merge_segment:
            filtered_merge_lines[line_idx].append(merge_segment)

    # Handle the merging
    already_merged = set()
    potential_merges = []
    for line_idx in filtered_merge_lines:
        potential_merges.extend(chain.from_iterable(filtered_merge_lines[line_idx]))
    potential_merges = set(potential_merges)

    # Provider lines that are not in any merge group should be outputted as-is
    out_provider_lines.extend(
        [
            hp
            for i, hp in enumerate(horizontal_provider_lines)
            if i not in potential_merges
        ]
    )

    def bbox_for_merge_section(
        merge_section: List[int],
        all_merge_sections: List[List[int]],
        text_line: PolygonBox,
    ):
        # Don't just take the whole detected line if we have multiple sections inside
        if len(all_merge_sections) == 1:
            text_line_overlaps = np.nonzero(overlaps[merge_section[0]])[0].tolist()
            merged_text_line: PolygonBox = text_lines[text_line_overlaps[0]]
            if len(text_line_overlaps) > 1:
                merged_text_line = merged_text_line.merge(
                    [text_lines[k] for k in text_line_overlaps[1:]]
                )
            return merged_text_line.rescale(image_size, page_size)
        else:
            poly = None
            for section_idx in merge_section:
                section_polygon = deepcopy(
                    horizontal_provider_lines[section_idx][1].line.polygon
                )
                if poly is None:
                    poly: PolygonBox = section_polygon
                else:
                    poly = poly.merge([section_polygon])
            return poly

    for line_idx in filtered_merge_lines:
        text_line = text_lines[line_idx]
        for merge_section in filtered_merge_lines[line_idx]:
            merge_section = [m for m in merge_section if m not in already_merged]
            if len(merge_section) == 0:
                continue
            elif len(merge_section) == 1:
                horizontal_provider_idx = merge_section[0]
                out_idx, merged_line = horizontal_provider_lines[
                    horizontal_provider_idx
                ]
                # Set the polygon to the detected line - This is because provider polygons are sometimes incorrect
                # TODO Add metadata for this
                merged_line.line.polygon = bbox_for_merge_section(
                    merge_section, filtered_merge_lines[line_idx], text_line
                )
                out_provider_lines.append((out_idx, merged_line))
                already_merged.add(merge_section[0])
            else:
                merge_section = sorted(merge_section)
                merged_line = None
                min_idx = min(merge_section)
                out_idx = horizontal_provider_lines[min_idx][0]
                for idx in merge_section:
                    provider_line = deepcopy(horizontal_provider_lines[idx][1])
                    if merged_line is None:
                        merged_line = provider_line
                    else:
                        # Combine the spans of the provider line with the merged line
                        merged_line = merged_line.merge(provider_line)
                    already_merged.add(idx)  # Prevent double merging
                # Set the polygon to the detected line - This is because provider polygons are sometimes incorrect
                # TODO Add metadata for this
                merged_line.line.polygon = bbox_for_merge_section(
                    merge_section, filtered_merge_lines[line_idx], text_line
                )
                out_provider_lines.append((out_idx, merged_line))

    # Sort to preserve original order
    out_provider_lines = sorted(out_provider_lines, key=lambda x: x[0])
    out_provider_lines = [p for _, p in out_provider_lines]

    # Detected lines that do not overlap with any provider lines should be outputted as-is
    LineClass = get_block_class(BlockTypes.Line)
    for j in range(len(detected_line_boxes)):
        if np.max(overlaps[:, j]) == 0:
            detected_line_polygon = PolygonBox.from_bbox(detected_line_boxes[j])
            out_provider_lines.append(
                ProviderOutput(
                    line=LineClass(
                        polygon=detected_line_polygon,
                        page_id=page_id,
                        text_extraction_method="surya",
                    ),
                    spans=[],
                    chars=[],
                )
            )

    return out_provider_lines


def assign_text_to_bboxes(text_lines, target_bboxes):
    if not text_lines or not target_bboxes:
        return {}

    text_line_bboxes = [t["bbox"] for t in text_lines]
    if hasattr(target_bboxes[0], "bbox"):
        target_bbox_list = [t.bbox for t in target_bboxes]
    else:
        target_bbox_list = target_bboxes

    intersection_matrix = matrix_intersection_area(text_line_bboxes, target_bbox_list)

    bbox_text = defaultdict(list)
    for text_line_idx, text_line in enumerate(text_lines):
        intersections = intersection_matrix[text_line_idx]
        if intersections.sum() == 0:
            continue

        max_intersection = intersections.argmax()
        bbox_text[max_intersection].append(text_line)

    return dict(bbox_text)
