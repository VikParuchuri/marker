import re
from typing import List

from nltk import wordpunct_tokenize

from marker.ocr.utils import alphanum_ratio
from marker.schema.page import Page
from marker.settings import settings


def should_ocr_page(page: Page, no_text: bool):
    detected_lines_found = detected_line_coverage(page)

    # OCR page if we got minimal text, or if we got too many spaces
    conditions = [
        no_text , # Full doc has no text, and needs full OCR
        (len(page.prelim_text) > 0 and detect_bad_ocr(page.prelim_text)),  # Bad OCR
        detected_lines_found is False, # didn't extract text for all detected lines
    ]

    return any(conditions) or settings.OCR_ALL_PAGES


def detect_bad_ocr(text, space_threshold=.6, newline_threshold=.5, alphanum_threshold=.4):
    if len(text) == 0:
        # Assume OCR failed if we have no text
        return True

    words = wordpunct_tokenize(text)
    words = [w for w in words if w.strip()]
    alpha_words = [word for word in words if word.isalnum()]

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
    if invalid_chars > max(3.0, len(text) * .02):
        return True

    return False


def no_text_found(pages: List[Page]):
    full_text = ""
    for page in pages:
        full_text += page.prelim_text
    return len(full_text.strip()) < 10


def detected_line_coverage(page: Page, intersect_thresh=.6, detection_thresh=.5):
    found_lines = 0
    total_lines = 0
    for detected_line in page.text_lines.bboxes:
        detected_bbox = detected_line.bbox
        for block in page.blocks:
            for line in block.lines:
                intersection_pct = line.intersection_pct(detected_bbox)
                if intersection_pct > intersect_thresh:
                    found_lines += 1
                total_lines += 1
    return found_lines / total_lines > detection_thresh
