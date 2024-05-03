from typing import List
from statistics import mean
import numpy as np

from marker.schema.page import Page


def find_bold_italic(pages: List[Page], bold_min_weight=550):
    font_weights = []
    for page in pages:
        for block in page.blocks:
            # We don't want to bias our font stats
            if block.block_type in ["Title", "Section-header"]:
                continue
            for line in block.lines:
                for span in line.spans:
                    if "bold" in span.font.lower():
                        span.bold = True
                    if "ital" in span.font.lower():
                        span.italic = True

                    font_weights.append(span.font_weight)
    font_weights = np.array(font_weights)
    bold_thresh = np.percentile(font_weights, 90)
    bold_thresh_lower = np.percentile(font_weights, 75)

    # If a lot of the text on the page is bold, don't bold it all
    if bold_thresh == bold_thresh_lower or bold_thresh < bold_min_weight:
        return

    for page in pages:
        for block in page.blocks:
            for line in block.lines:
                for span in line.spans:
                    if span.font_weight >= bold_thresh:
                        span.bold = True