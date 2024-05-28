import re
from typing import List

from marker.ocr.utils import alphanum_ratio
from marker.schema.bbox import rescale_bbox, box_intersection_pct
from marker.schema.page import Page
from marker.settings import settings


def should_ocr_page(page: Page, no_text: bool):
    detected_lines_found, total_lines = detected_line_coverage(page)

    # No reason to OCR page if it has no text lines
    if total_lines == 0:
        return False

    # OCR page if we got minimal text, or if we got too many spaces
    conditions = [
        no_text, # Full doc has no text, and needs full OCR
        (len(page.prelim_text) > 0 and detect_bad_ocr(page.prelim_text)),  # Bad OCR
        detected_lines_found is False, # didn't extract text for all detected lines
    ]

    return any(conditions) or settings.OCR_ALL_PAGES


def detect_bad_ocr(text, space_threshold=.7, newline_threshold=.6, alphanum_threshold=.3):
    if len(text) == 0:
        # Assume OCR failed if we have no text
        return True

    spaces = len(re.findall(r'\s+', text))
    alpha_chars = len(re.sub(r'\s+', '', text))
    if spaces / (alpha_chars + spaces) > space_threshold:
        return True

    newlines = len(re.findall(r'\n+', text))
    non_newlines = len(re.sub(r'\n+', '', text))
    if newlines / (newlines + non_newlines) > newline_threshold:
        return True

    if alphanum_ratio(text) < alphanum_threshold: # Garbled text
        return True

    invalid_chars = len([c for c in text if c in settings.INVALID_CHARS])
    if invalid_chars > max(6.0, len(text) * .03):
        return True

    return False


def no_text_found(pages: List[Page]):
    full_text = ""
    for page in pages:
        full_text += page.prelim_text
    return len(full_text.strip()) == 0


def detected_line_coverage(page: Page, intersect_thresh=.5, detection_thresh=.4):
    found_lines = 0
    for detected_line in page.text_lines.bboxes:
        # Get bbox and rescale to match dimensions of original page
        detected_bbox = detected_line.bbox
        detected_bbox = rescale_bbox(page.text_lines.image_bbox, page.bbox, detected_bbox)

        total_intersection = 0
        for block in page.blocks:
            for line in block.lines:
                intersection_pct = box_intersection_pct(detected_bbox, line.bbox)
                total_intersection += intersection_pct
        if total_intersection > intersect_thresh:
            found_lines += 1

    total_lines = len(page.text_lines.bboxes)
    if total_lines == 0:
        return True, 0

    return found_lines / total_lines > detection_thresh, total_lines
