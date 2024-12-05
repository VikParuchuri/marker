import atexit
import math
import re
from ctypes import byref, c_int, create_string_buffer
from typing import List, Set

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from ftfy import fix_text
from pdftext.postprocessing import handle_hyphens, postprocess_text
from PIL import Image

from marker.providers import BaseProvider, ProviderOutput, ProviderPageLines
from marker.providers.utils import alphanum_ratio
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.schema.text.span import Span
from marker.util import matrix_intersection_area


def get_fontname(textpage, i):
    font_name_str = ""
    flags = 0
    try:
        buffer_size = 256
        font_name = create_string_buffer(buffer_size)
        font_flags = c_int()

        length = pdfium_c.FPDFText_GetFontInfo(textpage, i, font_name, buffer_size, byref(font_flags))
        if length > buffer_size:
            font_name = create_string_buffer(length)
            pdfium_c.FPDFText_GetFontInfo(textpage, i, font_name, length, byref(font_flags))

        if length > 0:
            font_name_str = font_name.value.decode('utf-8')
            flags = font_flags.value
    except:
        pass
    return font_name_str, flags


def get_chars(textpage):
    chars = []
    start_idx = 0
    end_idx = 0
    for i in range(textpage.count_chars()):
        fontname, fontflag = get_fontname(textpage, i)
        text = chr(pdfium_c.FPDFText_GetUnicode(textpage, i))
        end_idx = start_idx + len(text)
        chars.append({
            "bbox": textpage.get_charbox(i, loose=False),
            "text": text,
            "rotation": pdfium_c.FPDFText_GetCharAngle(textpage, i),
            "font": {
                "name": fontname,
                "flags": fontflag,
                "size": pdfium_c.FPDFText_GetFontSize(textpage, i),
                "weight": pdfium_c.FPDFText_GetFontWeight(textpage, i),
            },
            "char_idx": i,
            "char_start_idx": start_idx,
            "char_end_idx": end_idx
        })
        start_idx = end_idx
    return chars


def merge_bboxes(bboxes, page_width, page_height, vertical_factor=0.01, horizontal_factor=0.02):
    vertical_threshold = page_height * vertical_factor
    horizontal_threshold = page_width * horizontal_factor

    lines = []
    current_line = []

    for bbox in bboxes:
        if not current_line:
            current_line.append(bbox)
            continue

        # Check if bbox is vertically aligned with the current line
        _, y0, _, y1 = bbox
        _, line_y0, _, line_y1 = current_line[-1]  # Last box in the current line

        if abs((y0 + y1) / 2 - (line_y0 + line_y1) / 2) <= vertical_threshold:
            current_line.append(bbox)
        else:
            lines.append(current_line)
            current_line = [bbox]

    if current_line:
        lines.append(current_line)

    merged_bboxes = []
    for line in lines:
        # Merge boxes
        merged_line = []
        current_box = line[0]

        for bbox in line[1:]:
            # Check if bbox is close enough horizontally to merge
            _, _, x1, _ = current_box
            x0, _, x1_next, _ = bbox

            if x0 - x1 <= horizontal_threshold:  # Merge
                current_box = (
                    min(current_box[0], bbox[0]),
                    min(current_box[1], bbox[1]),
                    max(current_box[2], bbox[2]),
                    max(current_box[3], bbox[3]),
                )
            else:
                merged_line.append(current_box)
                current_box = bbox

        merged_line.append(current_box)
        merged_bboxes.extend(merged_line)

    return merged_bboxes


def merge_chars_into_bboxes(line_bboxes, chars, tolerance=0):
    merged_lines = []
    remaining_chars = []

    char_idx = -1
    for line_bbox in line_bboxes:
        # Expand the line bbox by the tolerance
        line_x1, line_y1, line_x2, line_y2 = (
            line_bbox[0] - tolerance,
            line_bbox[1] - tolerance,
            line_bbox[2] + tolerance,
            line_bbox[3] + tolerance,
        )

        # Collect characters within this line
        line_chars = []
        remaining_chars = []

        for char in chars:
            char_x1, char_y1, char_x2, char_y2 = char["bbox"]
            # Check if char is within the expanded line bbox
            if (
                line_x1 <= char_x1 <= line_x2 and
                line_y1 <= char_y1 <= line_y2 and
                line_x1 <= char_x2 <= line_x2 and
                line_y1 <= char_y2 <= line_y2 and
                char["char_idx"] > char_idx
            ):
                line_chars.append(char)
                char_idx = char["char_idx"]
            else:
                remaining_chars.append(char)

        # Add merged line data to the result
        merged_lines.append({"bbox": line_bbox, "chars": line_chars})

        # Update the chars list with unmerged characters
        chars = remaining_chars

    if remaining_chars:
        line_ranges = []
        for line in merged_lines:
            if line["chars"]:
                char_indices = [char["char_idx"] for char in line["chars"]]
                line_ranges.append((min(char_indices), max(char_indices)))
            else:
                line_ranges.append((None, None))

        for char in sorted(remaining_chars, key=lambda c: c["char_idx"]):
            char_idx = char["char_idx"]
            added_to_line = False

            for i, (min_idx, max_idx) in enumerate(line_ranges):
                if min_idx is not None and max_idx is not None and min_idx <= char_idx <= max_idx:
                    merged_lines[i]["chars"].append(char)
                    added_to_line = True
                    break

            if not added_to_line:
                for i, (min_idx, max_idx) in reversed(list(enumerate(line_ranges))):
                    if min_idx is None or max_idx is None:
                        continue
                    if char_idx > max_idx and char["bbox"][0] >= merged_lines[i]["bbox"][2]:  # char appended to the end of a line
                        merged_lines[i]["chars"].append(char)
                        added_to_line = True
                        break

            if not added_to_line:
                for i, (min_idx, max_idx) in enumerate(line_ranges):
                    if min_idx is None or max_idx is None:
                        continue
                    if char_idx < min_idx and char["bbox"][0] <= merged_lines[i]["bbox"][0]:  # char appended to the beginning of a line
                        merged_lines[i]["chars"].insert(0, char)
                        added_to_line = True
                        break

            if not added_to_line:
                print("Could not find line for char", char)
                pass

    for line in merged_lines:
        if line["chars"]:
            line["chars"] = sorted(line["chars"], key=lambda c: c["char_idx"])

    return merged_lines


def get_pages(pdf: pdfium.PdfDocument, page_range: range, tolerance=0):
    pages = []
    for page_idx in page_range:
        page = pdf.get_page(page_idx)
        textpage = page.get_textpage()

        page_bbox = page.get_bbox()
        page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
        page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

        line_bboxes = []
        for i in range(textpage.count_rects()):
            bbox = textpage.get_rect(i)
            bbox = [bbox[0] - tolerance, bbox[1] - tolerance, bbox[2] + tolerance, bbox[3] + tolerance]
            line_bboxes.append(bbox)
        line_bboxes = merge_bboxes(line_bboxes, page_width, page_height)

        chars = get_chars(textpage)

        lines = []
        for line in merge_chars_into_bboxes(line_bboxes, chars):
            line["bbox"] = [line["bbox"][0], page_height - line["bbox"][3], line["bbox"][2], page_height - line["bbox"][1]]

            spans = []
            for char in line["chars"]:
                char["bbox"] = [char["bbox"][0], page_height - char["bbox"][3], char["bbox"][2], page_height - char["bbox"][1]]

                if not spans or (spans and any(char['font'][k] != spans[-1]['font'][k] for k in ['name', 'flags', 'size', 'weight'])):
                    spans.append({key: char[key] for key in char.keys()})
                else:
                    spans[-1]['text'] += char['text']
                    spans[-1]['char_end_idx'] = char['char_end_idx']
            lines.append({"bbox": line["bbox"], "spans": spans})

        pages.append({
            "page": page_idx,
            "bbox": page_bbox,
            "width": page_width,
            "height": page_height,
            "blocks": [{"lines": lines}]
        })
    return pages


class PdfProvider(BaseProvider):
    page_range: List[int] | None = None
    pdftext_workers: int = 4
    flatten_pdf: bool = True
    force_ocr: bool = False
    ocr_invalid_chars: tuple = (chr(0xfffd), "�")
    ocr_space_threshold: float = .7
    ocr_newline_threshold: float = .6
    ocr_alphanum_threshold: float = .3

    def __init__(self, filepath: str, config=None):
        super().__init__(filepath, config)

        self.doc: pdfium.PdfDocument = pdfium.PdfDocument(self.filepath)
        self.page_lines: ProviderPageLines = {i: [] for i in range(len(self.doc))}

        if self.page_range is None:
            self.page_range = range(len(self.doc))

        assert max(self.page_range) < len(self.doc) and min(self.page_range) >= 0, \
            f"Invalid page range, values must be between 0 and {len(self.doc) - 1}.  Min of provided page range is {min(self.page_range)} and max is {max(self.page_range)}."

        if self.force_ocr:
            # Manually assign page bboxes, since we can't get them from pdftext
            self.page_bboxes = {i: self.doc[i].get_bbox() for i in self.page_range}
        else:
            self.page_lines = self.pdftext_extraction()

        atexit.register(self.cleanup_pdf_doc)

    def __len__(self) -> int:
        return len(self.doc)

    def cleanup_pdf_doc(self):
        if self.doc is not None:
            self.doc.close()

    def font_flags_to_format(self, flags: int | None) -> Set[str]:
        if flags is None:
            return {"plain"}

        flag_map = {
            1: "FixedPitch",
            2: "Serif",
            3: "Symbolic",
            4: "Script",
            6: "Nonsymbolic",
            7: "Italic",
            17: "AllCap",
            18: "SmallCap",
            19: "ForceBold",
            20: "UseExternAttr"
        }
        set_flags = set()
        for bit_position, flag_name in flag_map.items():
            if flags & (1 << (bit_position - 1)):
                set_flags.add(flag_name)
        if not set_flags:
            set_flags.add("Plain")

        formats = set()
        if set_flags == {"Symbolic", "Italic"} or \
                set_flags == {"Symbolic", "Italic", "UseExternAttr"}:
            formats.add("math")
        elif set_flags == {"UseExternAttr"}:
            formats.add("plain")
        elif set_flags == {"Plain"}:
            formats.add("plain")
        else:
            if set_flags & {"Italic"}:
                formats.add("italic")
            if set_flags & {"ForceBold"}:
                formats.add("bold")
            if set_flags & {"FixedPitch", "Serif", "Script", "Nonsymbolic", "AllCap", "SmallCap", "UseExternAttr"}:
                formats.add("plain")
        return formats

    def font_names_to_format(self, font_name: str | None) -> Set[str]:
        formats = set()
        if font_name is None:
            return formats

        if "bold" in font_name.lower():
            formats.add("bold")
        if "ital" in font_name.lower():
            formats.add("italic")
        return formats

    def pdftext_extraction(self) -> ProviderPageLines:
        page_lines: ProviderPageLines = {}
        page_char_blocks = get_pages(self.doc, self.page_range)
        self.page_bboxes = {i: [0, 0, page["width"], page["height"]] for i, page in zip(self.page_range, page_char_blocks)}

        SpanClass: Span = get_block_class(BlockTypes.Span)
        LineClass: Line = get_block_class(BlockTypes.Line)
        for page in page_char_blocks:
            page_id = page["page"]
            lines: List[ProviderOutput] = []
            for block in page["blocks"]:
                for line in block["lines"]:
                    spans: List[Span] = []
                    for span in line["spans"]:
                        if not span["text"]:
                            continue
                        font_formats = self.font_flags_to_format(span["font"]["flags"]).union(self.font_names_to_format(span["font"]["name"]))
                        font_name = span["font"]["name"] or "Unknown"
                        font_weight = span["font"]["weight"] or 0
                        font_size = span["font"]["size"] or 0
                        polygon = PolygonBox.from_bbox(span["bbox"], ensure_nonzero_area=True)
                        spans.append(
                            SpanClass(
                                polygon=polygon,
                                text=fix_text(handle_hyphens(postprocess_text(span["text"]), keep_hyphens=True)),
                                font=font_name,
                                font_weight=font_weight,
                                font_size=font_size,
                                minimum_position=span["char_start_idx"],
                                maximum_position=span["char_end_idx"],
                                formats=list(font_formats),
                                page_id=page_id,
                                text_extraction_method="pdftext"
                            )
                        )
                    polygon = PolygonBox.from_bbox(line["bbox"], ensure_nonzero_area=True)
                    lines.append(
                        ProviderOutput(
                            line=LineClass(polygon=polygon, page_id=page_id),
                            spans=spans
                        )
                    )
            if self.check_line_spans(lines):
                page_lines[page_id] = lines
        return page_lines

    def check_line_spans(self, page_lines: List[ProviderOutput]) -> bool:
        page_spans = [span for line in page_lines for span in line.spans]
        if len(page_spans) == 0:
            return False

        text = ""
        for span in page_spans:
            text = text + " " + span.text
            text = text + "\n"
        if len(text.strip()) == 0:
            return False
        if self.detect_bad_ocr(text):
            return False
        return True

    def detect_bad_ocr(self, text):
        if len(text) == 0:
            # Assume OCR failed if we have no text
            return True

        spaces = len(re.findall(r'\s+', text))
        alpha_chars = len(re.sub(r'\s+', '', text))
        if spaces / (alpha_chars + spaces) > self.ocr_space_threshold:
            return True

        newlines = len(re.findall(r'\n+', text))
        non_newlines = len(re.sub(r'\n+', '', text))
        if newlines / (newlines + non_newlines) > self.ocr_newline_threshold:
            return True

        if alphanum_ratio(text) < self.ocr_alphanum_threshold:  # Garbled text
            return True

        invalid_chars = len([c for c in text if c in self.ocr_invalid_chars])
        if invalid_chars > max(6.0, len(text) * .03):
            return True

        return False

    @staticmethod
    def _render_image(pdf: pdfium.PdfDocument, idx: int, dpi: int) -> Image.Image:
        page = pdf[idx]
        page_rotation = 0
        try:
            page_rotation = page.get_rotation()
        except:
            pass
        image = page.render(scale=dpi / 72, draw_annots=False).to_pil().rotate(page_rotation, expand=True)
        image = image.convert("RGB")
        return image

    def get_images(self, idxs: List[int], dpi: int) -> List[Image.Image]:
        images = [self._render_image(self.doc, idx, dpi) for idx in idxs]
        return images

    def get_page_bbox(self, idx: int) -> PolygonBox | None:
        bbox = self.page_bboxes.get(idx)
        if bbox:
            return PolygonBox.from_bbox(bbox)

    def get_page_lines(self, idx: int) -> List[ProviderOutput]:
        return self.page_lines[idx]
