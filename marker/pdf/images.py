import pypdfium2 as pdfium
from pypdfium2 import PdfPage

from marker.schema.page import Page
from marker.schema.bbox import rescale_bbox
from marker.settings import settings


def render_image(page: pdfium.PdfPage, dpi):
    image = page.render(
        scale=dpi / 72,
        draw_annots=False
    ).to_pil()
    image = image.convert("RGB")
    return image


def render_bbox_image(page_obj: PdfPage, page: Page, bbox):
    png_image = render_image(page_obj, settings.IMAGE_DPI)
    # Rescale original pdf bbox bounds to match png image size
    png_bbox = [0, 0, png_image.size[0], png_image.size[1]]
    rescaled_merged = rescale_bbox(page.bbox, png_bbox, bbox)

    # Crop out only the equation image
    png_image = png_image.crop(rescaled_merged)
    png_image = png_image.convert("RGB")
    return png_image