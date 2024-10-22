from collections import defaultdict
from typing import List
import numpy as np
from sklearn.cluster import KMeans

from marker.settings import settings
from marker.schema.bbox import rescale_bbox
from marker.schema.block import bbox_from_lines
from marker.schema.page import Page


def split_heading_blocks(pages: List[Page]):
    # Heading lines can be combined into regular text blocks sometimes by pdftext
    # Split up heading lines into separate blocks properly
    for page in pages:
        page_heading_boxes = [b for b in page.layout.bboxes if b.label in ["Title", "Section-header"]]
        page_heading_boxes = [(rescale_bbox(page.layout.image_bbox, page.bbox, b.bbox), b.label) for b in page_heading_boxes]

        new_blocks = []
        for block_idx, block in enumerate(page.blocks):
            if block.block_type not in ["Text"]:
                new_blocks.append(block)
                continue

            heading_lines = []
            for line_idx, line in enumerate(block.lines):
                for (heading_box, label) in page_heading_boxes:
                    if line.intersection_pct(heading_box) > settings.BBOX_INTERSECTION_THRESH:
                        heading_lines.append((line_idx, label))
                        break

            if len(heading_lines) == 0:
                new_blocks.append(block)
                continue

            # Split up the block into separate blocks around headers
            start = 0
            for (heading_line, label) in heading_lines:
                if start < heading_line:
                    copied_block = block.copy()
                    copied_block.lines = block.lines[start:heading_line]
                    copied_block.bbox = bbox_from_lines(copied_block.lines)
                    new_blocks.append(copied_block)

                copied_block = block.copy()
                copied_block.lines = block.lines[heading_line:heading_line + 1]
                copied_block.block_type = label
                copied_block.bbox = bbox_from_lines(copied_block.lines)
                new_blocks.append(copied_block)

                start = heading_line + 1
                if start >= len(block.lines):
                    break

            # Add any remaining lines
            if start < len(block.lines):
                copied_block = block.copy()
                copied_block.lines = block.lines[start:]
                copied_block.bbox = bbox_from_lines(copied_block.lines)
                new_blocks.append(copied_block)

        page.blocks = new_blocks


def bucket_headings(line_heights, num_levels=settings.HEADING_LEVEL_COUNT):
    if len(line_heights) <= num_levels:
        return []

    data = np.asarray(line_heights).reshape(-1, 1)
    labels = KMeans(n_clusters=num_levels, random_state=0, n_init="auto").fit_predict(data)
    data_labels = np.concatenate([data, labels.reshape(-1, 1)], axis=1)
    data_labels = np.sort(data_labels, axis=0)

    cluster_means = {int(label): float(np.mean(data_labels[data_labels[:, 1] == label, 0])) for label in np.unique(labels)}
    label_max = None
    label_min = None
    heading_ranges = []
    prev_cluster = None
    for row in data_labels:
        value, label = row
        value = float(value)
        label = int(label)
        if prev_cluster is not None and label != prev_cluster:
            prev_cluster_mean = cluster_means[prev_cluster]
            cluster_mean = cluster_means[label]
            if cluster_mean * settings.HEADING_MERGE_THRESHOLD < prev_cluster_mean:
                heading_ranges.append((label_min, label_max))
                label_min = None
                label_max = None

        label_min = value if label_min is None else min(label_min, value)
        label_max = value if label_max is None else max(label_max, value)
        prev_cluster = label

    if label_min is not None:
        heading_ranges.append((label_min, label_max))

    heading_ranges = sorted(heading_ranges, reverse=True)

    return heading_ranges


def infer_heading_levels(pages: List[Page], height_tol=.99):
    all_line_heights = []
    for page in pages:
        for block in page.blocks:
            if block.block_type not in ["Title", "Section-header"]:
                continue

            all_line_heights.extend([l.height for l in block.lines])

    heading_ranges = bucket_headings(all_line_heights)

    for page in pages:
        for block in page.blocks:
            if block.block_type not in ["Title", "Section-header"]:
                continue

            block_heights = [l.height for l in block.lines]
            if len(block_heights) > 0:
                avg_height = sum(block_heights) / len(block_heights)
                for idx, (min_height, max_height) in enumerate(heading_ranges):
                    if avg_height >= min_height * height_tol:
                        block.heading_level = idx + 1
                        break

            if block.heading_level is None:
                block.heading_level = settings.HEADING_DEFAULT_LEVEL

