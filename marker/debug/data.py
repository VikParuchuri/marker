import base64
import json
import os
import zlib
from typing import List

from marker.schema import Page
from marker.settings import settings
from PIL import Image
import io


def dump_equation_debug_data(doc, images, converted_spans):
    if not settings.DEBUG_DATA_FOLDER or settings.DEBUG_LEVEL == 0:
        return

    if len(images) == 0:
        return

    # We attempted one conversion per image
    assert len(converted_spans) == len(images)

    data_lines = []
    for idx, (pil_image, converted_span) in enumerate(zip(images, converted_spans)):
        if converted_span is None:
            continue
        # Image is a BytesIO object
        img_bytes = io.BytesIO()
        pil_image.save(img_bytes, format="WEBP", lossless=True)
        b64_image = base64.b64encode(img_bytes.getvalue()).decode("utf-8")
        data_lines.append({
            "image": b64_image,
            "text": converted_span.text,
            "bbox": converted_span.bbox
        })

    # Remove extension from doc name
    doc_base = os.path.basename(doc.name).rsplit(".", 1)[0]

    debug_file = os.path.join(settings.DEBUG_DATA_FOLDER, f"{doc_base}_equations.json")
    with open(debug_file, "w+") as f:
        json.dump(data_lines, f)


def dump_bbox_debug_data(doc, blocks: List[Page]):
    if not settings.DEBUG_DATA_FOLDER or settings.DEBUG_LEVEL < 2:
        return

    # Remove extension from doc name
    doc_base = os.path.basename(doc.name).rsplit(".", 1)[0]

    debug_file = os.path.join(settings.DEBUG_DATA_FOLDER, f"{doc_base}_bbox.json")
    debug_data = []
    for idx, page_blocks in enumerate(blocks):
        page = doc[idx]

        pix = page.get_pixmap(dpi=settings.TEXIFY_DPI, annots=False, clip=page_blocks.bbox)
        png = pix.pil_tobytes(format="PNG")
        png_image = Image.open(io.BytesIO(png))
        width, height = png_image.size
        max_dimension = 6000
        if width > max_dimension or height > max_dimension:
            scaling_factor = min(max_dimension / width, max_dimension / height)
            png_image = png_image.resize((int(width * scaling_factor), int(height * scaling_factor)), Image.ANTIALIAS)

        img_bytes = io.BytesIO()
        png_image.save(img_bytes, format="WEBP", lossless=True, quality=100)
        b64_image = base64.b64encode(img_bytes.getvalue()).decode("utf-8")

        page_data = page_blocks.model_dump()
        page_data["image"] = b64_image
        debug_data.append(page_data)

    with open(debug_file, "w+") as f:
        json.dump(debug_data, f)



