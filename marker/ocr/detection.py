from typing import List

from pypdfium2 import PdfDocument
from surya.detection import batch_text_detection

from marker.pdf.images import render_image
from marker.schema.page import Page
from marker.settings import settings


def get_batch_size():
    if settings.DETECTOR_BATCH_SIZE is not None:
        return settings.DETECTOR_BATCH_SIZE
    elif settings.TORCH_DEVICE_MODEL == "cuda":
        return 4
    return 4


def surya_detection(doc: PdfDocument, pages: List[Page], det_model, batch_multiplier=1):
    processor = det_model.processor
    max_len = min(len(pages), len(doc))
    images = [render_image(doc[pnum], dpi=settings.SURYA_DETECTOR_DPI) for pnum in range(max_len)]

    predictions = batch_text_detection(images, det_model, processor, batch_size=int(get_batch_size() * batch_multiplier))
    for (page, pred) in zip(pages, predictions):
        page.text_lines = pred




