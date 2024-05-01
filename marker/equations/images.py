from typing import List

from PIL import Image, ImageDraw
from pypdfium2 import PdfPage

from marker.pdf.images import render_image
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.settings import settings


def mask_bbox(png_image, bbox: List[float], selected_bboxes: List[List[float]]):
    mask = Image.new('L', png_image.size, 0)  # 'L' mode for grayscale
    draw = ImageDraw.Draw(mask)
    first_x = bbox[0]
    first_y = bbox[1]
    bbox_height = bbox[3] - bbox[1]
    bbox_width = bbox[2] - bbox[0]

    for box in selected_bboxes:
        # Fit the box to the selected region
        new_box = (box[0] - first_x, box[1] - first_y, box[2] - first_x, box[3] - first_y)
        # Fit mask to image bounds versus the pdf bounds
        resized = (
           new_box[0] / bbox_width * png_image.size[0],
           new_box[1] / bbox_height * png_image.size[1],
           new_box[2] / bbox_width * png_image.size[0],
           new_box[3] / bbox_height * png_image.size[1]
        )
        draw.rectangle(resized, fill=255)

    result = Image.composite(png_image, Image.new('RGBA', png_image.size, 'white'), mask)
    return result


def get_masked_image(page_obj: PdfPage, page: Page, merged_bbox, selected_bboxes):
    rescaled_bboxes = []
    png_image = render_image(page_obj, settings.TEXIFY_DPI)
    # Rescale original pdf bbox bounds to match png image size
    png_bbox = [0, 0, png_image.size[0], png_image.size[1]]
    rescaled_merged = rescale_bbox(page.bbox, png_bbox, merged_bbox)

    # Crop out only the equation image
    png_image = png_image.crop(rescaled_merged)

    for selected_bbox in selected_bboxes:
        rescaled_bboxes.append(rescale_bbox(page.bbox, png_bbox, selected_bbox))

    png_image = mask_bbox(png_image, rescaled_merged, rescaled_bboxes)
    png_image = png_image.convert("RGB")
    return png_image
