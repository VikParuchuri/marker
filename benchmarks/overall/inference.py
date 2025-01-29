import io

import fitz as pymupdf
import tempfile
from bs4 import BeautifulSoup

from marker.converters.pdf import PdfConverter

def open_pymupdf(pdf_bytes):
    stream = io.BytesIO(pdf_bytes)
    return pymupdf.open(stream=stream)

def clip_pdf_to_bbox(doc, bbox, padding=1):
    page = doc[0]
    height, width = page.bound().height, page.bound().width
    remove_left = [0, 0, bbox[0] - padding, height]
    remove_top = [0, 0, width, bbox[1] - padding]
    remove_right = [bbox[2] + padding, 0, width, height]
    remove_bottom = [0, bbox[3] + padding, width, height]
    for remove in [remove_left, remove_top, remove_right, remove_bottom]:
        clip_rect = pymupdf.Rect(*remove)
        page.add_redact_annot(clip_rect)
    page.apply_redactions()

    clip_rect = pymupdf.Rect(*bbox)
    page.set_cropbox(clip_rect)
    return doc

def get_marker_block_html(marker_models: dict, gt_blocks: list, pdf_bytes: bytes):
    block_html = []
    for block in gt_blocks:
        bbox = block["bbox"]
        doc2 = open_pymupdf(pdf_bytes)
        clip_pdf_to_bbox(doc2, bbox)
        block_converter = PdfConverter(
            artifact_dict=marker_models,
            config={"page_range": [0], "force_layout_block": block["block_type"], "disable_tqdm": True},
            renderer="marker.renderers.html.HTMLRenderer"
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
            doc2.save(f)
            rendered = block_converter(f.name)
        html = rendered.html
        soup = BeautifulSoup(html, "html.parser")
        inner_html = str(soup.find("body").decode_contents())
        block_html.append(inner_html)
    return block_html