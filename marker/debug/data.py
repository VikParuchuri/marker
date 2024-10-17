import json
import math
import os
from typing import List

from marker.debug.render import render_on_image
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.settings import settings
from PIL import Image


def draw_layout_page_debug_images(fname, pages: List[Page]):
    # Remove extension from doc name
    doc_base = os.path.basename(fname).rsplit(".", 1)[0]

    debug_folder = os.path.join(settings.DEBUG_DATA_FOLDER, doc_base)
    os.makedirs(debug_folder, exist_ok=True)
    for idx, page in enumerate(pages):
        img_size = (int(math.ceil(page.text_lines.image_bbox[2])), int(math.ceil(page.text_lines.image_bbox[3])))
        png_image = Image.new("RGB", img_size, color="white")

        line_bboxes = []
        line_text = []
        for block in page.blocks:
            for line in block.lines:
                line_bboxes.append(rescale_bbox(page.bbox, page.text_lines.image_bbox, line.bbox))
                line_text.append(line.prelim_text)

        render_on_image(line_bboxes, png_image, labels=line_text, color="black", draw_bbox=False)
        pdf_image = png_image.copy()

        line_bboxes = [line.bbox for line in page.text_lines.bboxes]
        render_on_image(line_bboxes, png_image, color="blue")

        layout_boxes = [rescale_bbox(page.layout.image_bbox, page.text_lines.image_bbox, box.bbox) for box in page.layout.bboxes]
        layout_labels = [box.label for box in page.layout.bboxes]

        render_on_image(layout_boxes, png_image, labels=layout_labels, color="red")

        order_labels = [str(i) for i in range(len(page.layout.bboxes))]
        render_on_image(layout_boxes, png_image, labels=order_labels, color="green", draw_bbox=False, label_offset=5)

        debug_file = os.path.join(debug_folder, f"layout_page_{idx}.png")
        png_image.save(debug_file)

        # PDF Image

        block_bboxes = [rescale_bbox(page.bbox, page.text_lines.image_bbox, block.bbox) for block in page.blocks]
        block_labels = [block.block_type for block in page.blocks]
        render_on_image(block_bboxes, pdf_image, labels=block_labels, color="red")

        block_order = [str(i) for i in range(len(page.blocks))]
        render_on_image(block_bboxes, pdf_image, labels=block_order, color="green", draw_bbox=False, label_offset=5)

        debug_file = os.path.join(debug_folder, f"pdf_page_{idx}.png")
        pdf_image.save(debug_file)


def draw_pdf_page_debug_images(fname, pages: List[Page]):
    # Remove extension from doc name
    doc_base = os.path.basename(fname).rsplit(".", 1)[0]

    debug_folder = os.path.join(settings.DEBUG_DATA_FOLDER, doc_base)
    os.makedirs(debug_folder, exist_ok=True)
    for idx, page in enumerate(pages):
        img_size = (int(math.ceil(page.text_lines.image_bbox[2])), int(math.ceil(page.text_lines.image_bbox[3])))
        png_image = Image.new("RGB", img_size, color="white")

        line_bboxes = []
        line_text = []
        for block in page.blocks:
            for line in block.lines:
                line_bboxes.append(rescale_bbox(page.bbox, page.text_lines.image_bbox, line.bbox))
                line_text.append(line.prelim_text)




def draw_page_debug_images(fname, pages: List[Page]):
    if not settings.DEBUG:
        return

    draw_layout_page_debug_images(fname, pages)
    draw_pdf_page_debug_images(fname, pages)



def dump_bbox_debug_data(fname, pages: List[Page]):
    if not settings.DEBUG:
        return

    # Remove extension from doc name
    doc_base = os.path.basename(fname).rsplit(".", 1)[0]

    debug_file = os.path.join(settings.DEBUG_DATA_FOLDER, f"{doc_base}_bbox.json")
    debug_data = []
    for idx, page_blocks in enumerate(pages):
        page_data = page_blocks.model_dump(exclude=["images", "layout", "text_lines"])
        page_data["layout"] = page_blocks.layout.model_dump(exclude=["segmentation_map"])
        page_data["text_lines"] = page_blocks.text_lines.model_dump(exclude=["heatmap", "affinity_map"])
        debug_data.append(page_data)

    with open(debug_file, "w+") as f:
        json.dump(debug_data, f)
    print(f"Dumped bbox debug data to {debug_file}")



