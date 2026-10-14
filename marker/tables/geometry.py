"""Capture PDF/OCR coordinates before table processing discards the text layer."""

import csv
import ctypes
import io
import math
import re
import shutil
import subprocess

import pypdfium2 as pdfium

from marker.schema import BlockTypes
from marker.tables.validation import intersects

CAPTION = re.compile(r"^(?:Продолжение\s+|Окончание\s+)?[Тт]аблиц[аы]\s+([А-ЯA-Z]?\.?\d+(?:\.\d+)?[а-яa-z]?)")


def crop_table(page, block):
    image = page.get_image(highres=True)
    sx, sy = image.width / page.polygon.width, image.height / page.polygon.height
    x0, y0, x1, y1 = block.polygon.bbox
    px0, py0 = page.polygon.bbox[:2]
    crop = [max(0, math.floor((x0 - px0) * sx)), max(0, math.floor((y0 - py0) * sy)),
            min(image.width, math.ceil((x1 - px0) * sx)), min(image.height, math.ceil((y1 - py0) * sy))]
    return image.crop(crop), crop, (sx, sy)


def pdf_tokens(raw_page, table_bbox):
    """Split at spatial gaps while retaining the actual character boxes."""
    tokens = []
    for block in raw_page.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars") or []
                if not chars:
                    if span.get("text", "").strip() and intersects(span["bbox"], table_bbox):
                        tokens.append((span["text"].strip(), span["bbox"]))
                    continue
                current, bounds = "", None
                for char in chars:
                    box = char["bbox"]
                    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                    within = table_bbox[0] <= cx <= table_bbox[2] and table_bbox[1] <= cy <= table_bbox[3]
                    gap = max(1, (box[3] - box[1]) * 0.5)
                    if not within or (bounds and (box[0] - bounds[2] > gap
                                                  or not intersects([box[0], box[1], box[2], box[3]],
                                                                    [box[0], bounds[1], box[2], bounds[3]]))):
                        if current.strip():
                            tokens.append((current.strip(), bounds))
                        current, bounds = "", None
                    if within:
                        current += char.get("char", "")
                        bounds = box.copy() if bounds is None else [min(bounds[0], box[0]), min(bounds[1], box[1]),
                                                                  max(bounds[2], box[2]), max(bounds[3], box[3])]
                if current.strip():
                    tokens.append((current.strip(), bounds))
    return tokens


def caption_hint(page, block):
    candidates = []
    if page.pdftext_page:
        for source in page.pdftext_page.get("blocks", []):
            for line in source.get("lines", []):
                text = " ".join(s.get("text", "") for s in line.get("spans", [])).strip()
                bbox = line.get("bbox", [0, 0, 0, 0])
                if CAPTION.match(text) and "редакци" not in text.lower():
                    gap = block.polygon.y_start - bbox[3]
                    if -2 <= gap <= 100:
                        candidates.append((gap, text))
    return min(candidates)[1] if candidates else ""


def ocr_tokens(image, languages):
    """Optional coordinate OCR for scans; never invent positions from HTML."""
    binary = shutil.which("tesseract")
    if binary is None:
        return [], ["ocr_coordinates_unavailable: install Tesseract with rus+eng language data"]
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    try:
        process = subprocess.run([binary, "stdin", "stdout", "-l", languages, "tsv"],
                                 input=stream.getvalue(), capture_output=True, timeout=120, check=True)
    except (subprocess.SubprocessError, OSError):
        return [], ["ocr_coordinates_unavailable: Tesseract failed"]
    tokens = []
    for row in csv.DictReader(io.StringIO(process.stdout.decode("utf-8")), delimiter="\t"):
        if not row.get("text", "").strip():
            continue
        x, y, w, h = [int(row[k]) for k in ("left", "top", "width", "height")]
        tokens.append((row["text"], [x, y, x + w, y + h], float(row["conf"])))
    return tokens, [] if tokens else ["ocr_coordinates_unavailable: no words detected"]


def vector_rules(filepath, page_id, table_bbox, transform):
    """Axis-aligned PDF path segments, including paths inside Form objects."""
    rules = []
    if not filepath.lower().endswith(".pdf"):
        return rules
    try:
        with pdfium.PdfDocument(filepath) as pdf:
            page = pdf[page_id]
            if page.get_rotation() != 0:
                page.close()
                return rules  # The image and text coordinates remain available.
            left, bottom, right, top = page.get_bbox()
            for obj in page.get_objects():
                if obj.type != pdfium.raw.FPDF_PAGEOBJ_PATH:
                    continue
                matrix, prev, first = obj.get_matrix(), None, None
                for i in range(pdfium.raw.FPDFPath_CountSegments(obj)):
                    segment = pdfium.raw.FPDFPath_GetPathSegment(obj, i)
                    x, y = ctypes.c_float(), ctypes.c_float()
                    if not pdfium.raw.FPDFPathSegment_GetPoint(segment, x, y):
                        continue
                    point = matrix.on_point(x.value, y.value)
                    point = (point[0] - left, top - point[1])
                    kind = pdfium.raw.FPDFPathSegment_GetType(segment)
                    if kind == pdfium.raw.FPDF_SEGMENT_MOVETO:
                        first = point
                    if kind == pdfium.raw.FPDF_SEGMENT_LINETO and prev:
                        add_rule(rules, prev, point, table_bbox, transform)
                    if pdfium.raw.FPDFPathSegment_GetClose(segment) and first:
                        add_rule(rules, point, first, table_bbox, transform)
                    prev = point
            page.close()
    except (OSError, RuntimeError, ValueError, pdfium.PdfiumError):
        # Vector rules are an optional hint, never a replacement for the image.
        return []
    return rules


def add_rule(rules, a, b, bbox, transform):
    orient = "h" if abs(a[1] - b[1]) < 0.5 else "v" if abs(a[0] - b[0]) < 0.5 else None
    if orient is None or max(abs(a[0] - b[0]), abs(a[1] - b[1])) < 8:
        return
    if not (bbox[0] - 1 <= min(a[0], b[0]) <= max(a[0], b[0]) <= bbox[2] + 1
            and bbox[1] - 1 <= min(a[1], b[1]) <= max(a[1], b[1]) <= bbox[3] + 1):
        return
    coords = transform([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])])
    rules.append(dict(orient=orient, x0=coords[0], y0=coords[1], x1=coords[2], y1=coords[3]))


def capture_geometry(document, page, block, use_ocr=True, languages="rus+eng"):
    image, crop, (sx, sy) = crop_table(page, block)
    px0, py0 = page.polygon.bbox[:2]

    def transform(box):
        return [round((box[0] - px0) * sx - crop[0], 2), round((box[1] - py0) * sy - crop[1], 2),
                round((box[2] - px0) * sx - crop[0], 2), round((box[3] - py0) * sy - crop[1], 2)]

    region_id, page_no = str(block.id), page.page_id + 1
    result = {"region": {"region_id": region_id, "page": page_no, "bbox": [0, 0, image.width, image.height]},
              "page_bbox": block.polygon.bbox, "crop_pixel_bbox": crop, "image_size": list(image.size),
              "caption_hint": caption_hint(page, block), "text_blocks": [], "rules": [], "warnings": []}
    tokens = pdf_tokens(page.pdftext_page or {}, block.polygon.bbox)
    if tokens and page.text_extraction_method != "surya":
        entries = [(text, transform(box), "text", "pdftext", None) for text, box in tokens]
    else:
        entries = []
        for child in page.current_children:
            if (child.block_type == BlockTypes.Span and child.text_extraction_method == "surya"
                    and intersects(child.polygon.bbox, block.polygon.bbox)):
                entries.append((child.text, transform(child.polygon.bbox), "formula" if child.math else "text", "ocr", None))
        if not entries and use_ocr:
            recognized, warnings = ocr_tokens(image, languages)
            entries = [(text, box, "text", "ocr", confidence) for text, box, confidence in recognized]
            result["warnings"].extend(warnings)
        elif not entries:
            result["warnings"].append("ocr_coordinates_unavailable: coordinate OCR disabled")
    for i, (text, box, kind, source, confidence) in enumerate(entries):
        # Round-off at crop boundaries is clipped consistently with the crop.
        box = [max(0, box[0]), max(0, box[1]), min(image.width, box[2]), min(image.height, box[3])]
        if box[2] <= box[0] or box[3] <= box[1] or not text.strip():
            continue
        result["text_blocks"].append({"id": f"{region_id}:b{i}", "region_id": region_id, "page": page_no,
                                      "bbox": box, "type": kind, "text": text, "source": source,
                                      "confidence": confidence})
    result["rules"] = vector_rules(document.filepath, page.page_id, block.polygon.bbox, transform)
    return result
