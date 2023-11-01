from collections import Counter, defaultdict
from itertools import chain

from sklearn.cluster import DBSCAN, HDBSCAN
import numpy as np

from collections import Counter
from copy import deepcopy

from marker.schema import Page
from typing import List


def filter_common_elements(lines, page_count):
    text = [s.text for line in lines for s in line.spans]
    counter = Counter(text)
    common = [k for k, v in counter.items() if v > page_count * .4]
    bad_span_ids = [s.text for line in lines for s in line.spans if s.span_id in common]
    return bad_span_ids


def filter_header_footer(all_page_blocks, max_selected_lines=2):
    first_lines = []
    last_lines = []
    for page in all_page_blocks:
        nonblank_lines = page.get_nonblank_lines()
        first_lines.extend(nonblank_lines[:max_selected_lines])
        last_lines.extend(nonblank_lines[-max_selected_lines:])

    bad_span_ids = filter_common_elements(first_lines, len(all_page_blocks))
    bad_span_ids += filter_common_elements(last_lines, len(all_page_blocks))
    return bad_span_ids


def categorize_blocks(all_page_blocks: List[Page]):
    spans = list(chain.from_iterable([p.get_nonblank_spans() for p in all_page_blocks]))
    X = np.array(
        [(*s.bbox, len(s.text)) for s in spans]
    )

    dbscan = DBSCAN(eps=.1, min_samples=5)
    dbscan.fit(X)
    labels = dbscan.labels_
    label_chars = defaultdict(int)
    for i, label in enumerate(labels):
        label_chars[label] += len(spans[i].text)

    most_common_label = None
    most_chars = 0
    for i in label_chars.keys():
        if label_chars[i] > most_chars:
            most_common_label = i
            most_chars = label_chars[i]

    labels = [0 if label == most_common_label else 1 for label in labels]
    bad_span_ids = [spans[i].span_id for i in range(len(spans)) if labels[i] == 1]

    return bad_span_ids


