from typing import List

from marker.schema.page import Page


def get_pdf_toc(doc, max_depth=15):
    toc = doc.get_toc(max_depth=max_depth)
    toc_list = []
    for item in toc:
        list_item = {
            "title": item.title,
            "level": item.level,
            "page": item.page_index,
        }
        toc_list.append(list_item)
    return toc_list


def compute_toc(pages: List[Page]):
    toc = []
    for page in pages:
        for block in page.blocks:
            if block.block_type in ["Title", "Section-header"]:
                toc.append({
                    "title": block.prelim_text,
                    "level": block.heading_level,
                    "page": page.pnum
                })
    return toc
