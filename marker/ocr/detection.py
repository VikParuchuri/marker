from typing import List

from pypdfium2 import PdfDocument
from surya.detection import batch_text_detection

from marker.pdf.images import render_image
from marker.schema.page import Page
from marker.settings import settings


def surya_detection(doc: PdfDocument, pages: List[Page], det_model):
    processor = det_model.processor
    max_len = min(len(pages), len(doc))
    images = [render_image(doc[pnum], dpi=settings.SURYA_DETECTOR_DPI) for pnum in range(max_len)]

    predictions = batch_text_detection(images, det_model, processor)
    for (page, pred) in zip(pages, predictions):
        page.text_lines = pred




