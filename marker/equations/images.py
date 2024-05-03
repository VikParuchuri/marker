from pypdfium2 import PdfPage

from marker.pdf.images import render_image
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.settings import settings


def get_equation_image(page_obj: PdfPage, page: Page, bbox):
    rescaled_bboxes = []
    png_image = render_image(page_obj, settings.TEXIFY_DPI)
    # Rescale original pdf bbox bounds to match png image size
    png_bbox = [0, 0, png_image.size[0], png_image.size[1]]
    rescaled_merged = rescale_bbox(page.bbox, png_bbox, bbox)

    # Crop out only the equation image
    png_image = png_image.crop(rescaled_merged)
    png_image = png_image.convert("RGB")
    return png_image
