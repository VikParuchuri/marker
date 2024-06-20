from typing import List

from surya.layout import batch_layout_detection

from marker.pdf.images import render_image
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.settings import settings


def get_batch_size():
    if settings.LAYOUT_BATCH_SIZE is not None:
        return settings.LAYOUT_BATCH_SIZE
    elif settings.TORCH_DEVICE_MODEL == "cuda":
        return 6
    return 6


def surya_layout(doc, pages: List[Page], layout_model, batch_multiplier=1):
    images = [render_image(doc[pnum], dpi=settings.SURYA_LAYOUT_DPI) for pnum in range(len(pages))]
    text_detection_results = [p.text_lines for p in pages]

    processor = layout_model.processor
    layout_results = batch_layout_detection(images, layout_model, processor, detection_results=text_detection_results, batch_size=int(get_batch_size() * batch_multiplier))
    for page, layout_result in zip(pages, layout_results):
        page.layout = layout_result


def annotate_block_types(pages: List[Page]):
    for page in pages:
        max_intersections = {}
        for i, block in enumerate(page.blocks):
            for j, layout_block in enumerate(page.layout.bboxes):
                layout_bbox = layout_block.bbox
                layout_bbox = rescale_bbox(page.layout.image_bbox, page.bbox, layout_bbox)
                intersection_pct = block.intersection_pct(layout_bbox)
                if i not in max_intersections:
                    max_intersections[i] = (intersection_pct, j)
                elif intersection_pct > max_intersections[i][0]:
                    max_intersections[i] = (intersection_pct, j)

        for i, block in enumerate(page.blocks):
            block = page.blocks[i]
            block_type = "Text"
            if i in max_intersections:
                j = max_intersections[i][1]
                block_type = page.layout.bboxes[j].label
            block.block_type = block_type