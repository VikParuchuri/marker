import re
from collections import Counter
from rapidfuzz import fuzz

from marker.schema.merged import FullyMergedBlock
from typing import List, Tuple


def filter_common_elements(lines, page_count, threshold=.6):
    # We can't filter if we don't have enough pages to find common elements
    if page_count < 3:
        return []
    text = [s.text for line in lines for s in line.spans if len(s.text) > 4]
    counter = Counter(text)
    common = [k for k, v in counter.items() if v > page_count * threshold]
    bad_span_ids = [s.span_id for line in lines for s in line.spans if s.text in common]
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


def replace_leading_trailing_digits(string, replacement):
    string = re.sub(r'^\d+', replacement, string)
    string = re.sub(r'\d+$', replacement, string)
    return string


def find_overlap_elements(lst: List[Tuple[str, int]], string_match_thresh=.9, min_overlap=.05) -> List[int]:
    # Initialize a list to store the elements that meet the criteria
    result = []
    titles = [l[0] for l in lst]

    for i, (str1, id_num) in enumerate(lst):
        overlap_count = 0  # Count the number of elements that overlap by at least 80%

        for j, str2 in enumerate(titles):
            if i != j and fuzz.ratio(str1, str2) >= string_match_thresh * 100:
                overlap_count += 1

        # Check if the element overlaps with at least 50% of other elements
        if overlap_count >= max(3.0, len(lst) * min_overlap):
            result.append(id_num)

    return result


def filter_common_titles(merged_blocks: List[FullyMergedBlock]) -> List[FullyMergedBlock]:
    titles = []
    for i, block in enumerate(merged_blocks):
        if block.block_type in ["Title", "Section-header"]:
            text = block.text
            if text.strip().startswith("#"):
                text = re.sub(r'#+', '', text)
            text = text.strip()
            # Remove page numbers from start/end
            text = replace_leading_trailing_digits(text, "").strip()
            titles.append((text, i))

    bad_block_ids = find_overlap_elements(titles)

    new_blocks = []
    for i, block in enumerate(merged_blocks):
        if i in bad_block_ids:
            continue
        new_blocks.append(block)

    return new_blocks




