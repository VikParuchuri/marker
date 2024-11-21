from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document

from typing import Dict, List
import numpy as np
from sklearn.cluster import KMeans
from sklearn.exceptions import ConvergenceWarning

# Ignore sklearn warning about not converging
import warnings
warnings.filterwarnings("ignore", category=ConvergenceWarning)


class SectionHeaderProcessor(BaseProcessor):
    block_types = (BlockTypes.SectionHeader, )
    level_count = 4
    merge_threshold = .25
    default_level = 2
    height_tolerance = .99

    def __call__(self, document: Document):
        line_heights: Dict[int, List[float]] = {}
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                line_heights[block.block_id] = []
                if block.structure is not None:
                    line_heights[block.block_id] = [document.get_block(l).polygon.height for l in block.structure if l.block_type == BlockTypes.Line]

        flat_line_heights = [h for heights in line_heights.values() for h in heights]
        heading_ranges = self.bucket_headings(flat_line_heights)

        for page in document.pages:
            for block in page.children:
                if block.block_type not in self.block_types:
                    continue

                block_heights = line_heights[block.block_id]
                if len(block_heights) > 0:
                    avg_height = sum(block_heights) / len(block_heights)
                    for idx, (min_height, max_height) in enumerate(heading_ranges):
                        if avg_height >= min_height * self.height_tolerance:
                            block.heading_level = idx + 1
                            break

                if block.heading_level is None:
                    block.heading_level = self.default_level

    def bucket_headings(self, line_heights: List[float], num_levels=4):
        if len(line_heights) <= self.level_count:
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
                if cluster_mean * self.merge_threshold < prev_cluster_mean:
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
