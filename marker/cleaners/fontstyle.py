from typing import List

from marker.schema.page import Page


def find_bold_italic(pages: List[Page], bold_min_weight=600):
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

    if len(font_weights) == 0:
        return

    for page in pages:
        for block in page.blocks:
            for line in block.lines:
                for span in line.spans:
                    if span.font_weight >= bold_min_weight:
                        span.bold = True