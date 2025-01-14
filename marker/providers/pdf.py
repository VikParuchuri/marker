import atexit
import ctypes
import math
import re
from typing import Annotated, List, Optional, Set, Tuple

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from ftfy import fix_text
from pdftext.extraction import dictionary_output
from pdftext.schema import Bbox
from PIL import Image

from marker.providers import BaseProvider, ProviderOutput, ProviderPageLines
from marker.providers.utils import alphanum_ratio
from marker.schema import BlockTypes
from marker.schema.polygon import PolygonBox
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.schema.text.span import Span
from marker.util import matrix_intersection_area


class PdfProvider(BaseProvider):
    """
    A provider for PDF files.
    """

    page_range: Annotated[
        Optional[List[int]],
        "The range of pages to process.",
        "Default is None, which will process all pages."
    ] = None
    pdftext_workers: Annotated[
        int,
        "The number of workers to use for pdftext.",
    ] = 4
    flatten_pdf: Annotated[
        bool,
        "Whether to flatten the PDF structure.",
    ] = True
    force_ocr: Annotated[
        bool,
        "Whether to force OCR on the whole document.",
    ] = False
    ocr_invalid_chars: Annotated[
        tuple,
        "The characters to consider invalid for OCR.",
    ] = (chr(0xfffd), "�")
    ocr_space_threshold: Annotated[
        float,
        "The minimum ratio of spaces to non-spaces to detect bad text.",
    ] = .7
    ocr_newline_threshold: Annotated[
        float,
        "The minimum ratio of newlines to non-newlines to detect bad text.",
    ] = .6
    ocr_alphanum_threshold: Annotated[
        float,
        "The minimum ratio of alphanumeric characters to non-alphanumeric characters to consider an alphanumeric character.",
    ] = .3
    image_threshold: Annotated[
        float,
        "The minimum coverage ratio of the image to the page to consider skipping the page.",
    ] = .65
    strip_existing_ocr: Annotated[
        bool,
        "Whether to strip existing OCR text from the PDF.",
    ] = False
    disable_links: Annotated[
        bool,
        "Whether to disable links.",
    ] = False

    def __init__(self, filepath: str, config=None):
        super().__init__(filepath, config)

        self.doc: pdfium.PdfDocument = pdfium.PdfDocument(self.filepath)
        self.page_lines: ProviderPageLines = {i: [] for i in range(len(self.doc))}
        self.refs = {}

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

    def font_flags_to_format(self, flags: Optional[int]) -> Set[str]:
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
            formats.add("plain")
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
        page_char_blocks = dictionary_output(
            self.filepath,
            page_range=self.page_range,
            keep_chars=True,
            workers=self.pdftext_workers,
            flatten_pdf=self.flatten_pdf,
            quote_loosebox=False
        )
        self.page_bboxes = {i: [0, 0, page["width"], page["height"]] for i, page in zip(self.page_range, page_char_blocks)}

        SpanClass: Span = get_block_class(BlockTypes.Span)
        LineClass: Line = get_block_class(BlockTypes.Line)

        if not self.disable_links:
            for page in page_char_blocks:
                self.merge_links(page)

            for page in page_char_blocks:
                self.merge_refs(page)

        for page in page_char_blocks:
            page_id = page["page"]
            lines: List[ProviderOutput] = []
            if not self.check_page(page_id):
                continue

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
                                text=fix_text(span["text"]),
                                font=font_name,
                                font_weight=font_weight,
                                font_size=font_size,
                                minimum_position=span["char_start_idx"],
                                maximum_position=span["char_end_idx"],
                                formats=list(font_formats),
                                page_id=page_id,
                                text_extraction_method="pdftext",
                                url=span.get("url"),
                                anchors=span.get("anchors"),
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

    def merge_links(self, page):
        page_id = page["page"]

        links = self.get_links(page_id)

        spans = [span for block in page['blocks'] for line in block['lines'] for span in line['spans']]
        span_bboxes = [span['bbox'] for span in spans]
        link_bboxes = [link['bbox'] for link in links]
        intersection_matrix = matrix_intersection_area(link_bboxes, span_bboxes)

        span_link_map = {}
        for link_idx, link in enumerate(links):
            intersection_link = intersection_matrix[link_idx]
            if intersection_link.sum() == 0:
                continue

            max_intersection = intersection_link.argmax()
            span = spans[max_intersection]

            if link['dest_page'] is None:
                continue

            dest_page = link['dest_page']
            self.refs.setdefault(dest_page, [])
            link['url'] = f"#page-{dest_page}"
            if link['dest_pos']:
                dest_pos = link['dest_pos']
            else:
                # Don't link to self if there is no dest_pos
                if dest_page == page_id:
                    continue
                dest_pos = [0.0, 0.0]

            if dest_pos not in self.refs[dest_page]:
                self.refs[dest_page].append(dest_pos)

            link['url'] += f"-{self.refs[dest_page].index(dest_pos)}"

            span_link_map.setdefault(max_intersection, [])
            span_link_map[max_intersection].append(link)

        span_idx = 0
        for block in page["blocks"]:
            for line in block["lines"]:
                spans = []
                for span in line["spans"]:
                    if span_idx in span_link_map:
                        spans.extend(self.break_spans(span, span_link_map[span_idx]))
                    else:
                        spans.append(span)
                    span_idx += 1
                line['spans'] = spans

    def merge_refs(self, page):
        page_id = page["page"]

        refs = self.refs.get(page_id, [])
        if not refs:
            return

        spans = [span for block in page['blocks'] for line in block['lines'] for span in line['spans']]
        if not spans:
            return

        span_starts = np.array([span['bbox'][:2] for span in spans])
        ref_starts = np.array(refs)

        distances = np.linalg.norm(span_starts[:, np.newaxis, :] - ref_starts[np.newaxis, :, :], axis=2)

        for ref_idx in range(len(ref_starts)):
            span_idx = np.argmin(distances[:, ref_idx])
            spans[span_idx].setdefault('anchors', [])
            spans[span_idx]['anchors'].append(f"page-{page_id}-{ref_idx}")

    def break_spans(self, orig_span, links):
        spans = []
        span = None
        link_bboxes = [Bbox(link['bbox']) for link in links]

        for char in orig_span['chars']:
            char_bbox = Bbox(char['bbox'])
            intersections = []
            for i, link_bbox in enumerate(link_bboxes):
                area = link_bbox.intersection_area(char_bbox)
                if area > 0:
                    intersections.append((area, links[i]))

            current_url = ''
            if intersections:
                intersections.sort(key=lambda x: x[0], reverse=True)
                current_url = intersections[0][1]['url']

            if not span or current_url != span['url']:
                span = {
                    "bbox": char_bbox,
                    "text": char["char"],
                    "rotation": char["rotation"],
                    "font": char["font"],
                    "char_start_idx": char["char_idx"],
                    "char_end_idx": char["char_idx"],
                    "chars": [char],
                    "url": current_url
                }
                spans.append(span)
            else:
                span['text'] += char['char']
                span['char_end_idx'] = char['char_idx']
                span['bbox'] = span['bbox'].merge(char_bbox)
                span['chars'].append(char)

        for span in spans:
            span['bbox'] = span['bbox'].bbox

        return spans

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

    def check_page(self, page_id: int) -> bool:
        page = self.doc.get_page(page_id)
        page_bbox = PolygonBox.from_bbox(page.get_bbox())
        page_objs = list(page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_TEXT, pdfium_c.FPDF_PAGEOBJ_IMAGE]))

        # if we do not see any text objects in the pdf, we can skip this page
        if not any([obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT for obj in page_objs]):
            return False

        if self.strip_existing_ocr:
            # If any text objects on the page are in invisible render mode, skip this page
            for text_obj in filter(lambda obj: obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT, page_objs):
                if pdfium_c.FPDFTextObj_GetTextRenderMode(text_obj) in [pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE, pdfium_c.FPDF_TEXTRENDERMODE_UNKNOWN]:
                    return False

            non_embedded_fonts = []
            empty_fonts = []
            font_map = {}
            for text_obj in filter(lambda obj: obj.type == pdfium_c.FPDF_PAGEOBJ_TEXT, page_objs):
                font = pdfium_c.FPDFTextObj_GetFont(text_obj)
                font_name = self.get_fontname(font)

                # we also skip pages without embedded fonts and fonts without names
                non_embedded_fonts.append(pdfium_c.FPDFFont_GetIsEmbedded(font) == 0)
                empty_fonts.append(not font_name or font_name == "GlyphLessFont")
                if font_name not in font_map:
                    font_map[font_name or 'Unknown'] = font

            if all(non_embedded_fonts) or all(empty_fonts):
                return False

            # if we see very large images covering most of the page, we can skip this page
            for img_obj in filter(lambda obj: obj.type == pdfium_c.FPDF_PAGEOBJ_IMAGE, page_objs):
                img_bbox = PolygonBox.from_bbox(img_obj.get_pos())
                if page_bbox.intersection_pct(img_bbox) >= self.image_threshold:
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
        image = page.render(scale=dpi / 72, draw_annots=False).to_pil()
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

    def get_fontname(self, font) -> str:
        font_name = ""
        buffer_size = 256

        try:
            font_name_buffer = ctypes.create_string_buffer(buffer_size)
            length = pdfium_c.FPDFFont_GetBaseFontName(font, font_name_buffer, buffer_size)
            if length < buffer_size:
                font_name = font_name_buffer.value.decode("utf-8")
            else:
                font_name_buffer = ctypes.create_string_buffer(length)
                pdfium_c.FPDFFont_GetBaseFontName(font, font_name_buffer, length)
                font_name = font_name_buffer.value.decode("utf-8")
        except:
            pass

        return font_name

    def get_dest_position(self, dest) -> Optional[Tuple[float, float]]:
        has_x = ctypes.c_int()
        has_y = ctypes.c_int()
        has_zoom = ctypes.c_int()
        x_coord = ctypes.c_float()
        y_coord = ctypes.c_float()
        zoom_level = ctypes.c_float()
        success = pdfium_c.FPDFDest_GetLocationInPage(
            dest,
            ctypes.byref(has_x),
            ctypes.byref(has_y),
            ctypes.byref(has_zoom),
            ctypes.byref(x_coord),
            ctypes.byref(y_coord),
            ctypes.byref(zoom_level)
        )
        if success:
            if has_x.value and has_y.value:
                return x_coord.value, y_coord.value
        else:
            return None

    def rect_to_scaled_bbox(self, rect, page_bbox, page_height, page_width, page_rotation) -> List[float]:
        cx_start, cy_start, cx_end, cy_end = rect
        cx_start -= page_bbox[0]
        cx_end -= page_bbox[0]
        cy_start -= page_bbox[1]
        cy_end -= page_bbox[1]

        ty_start = page_height - cy_start
        ty_end = page_height - cy_end

        bbox = [min(cx_start, cx_end), min(ty_start, ty_end), max(cx_start, cx_end), max(ty_start, ty_end)]
        return Bbox(bbox).rotate(page_width, page_height, page_rotation).bbox

    def xy_to_scaled_pos(self, x, y, page_bbox, page_height, page_width, page_rotation, expand_by=1) -> List[float]:
        return self.rect_to_scaled_bbox([x - expand_by, y - expand_by, x + expand_by, y + expand_by], page_bbox, page_height, page_width, page_rotation)[:2]

    def get_links(self, page_idx):
        urls = []
        page = self.doc[page_idx]
        page_bbox: List[float] = page.get_bbox()
        page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
        page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))
        page_rotation = 0
        try:
            page_rotation = page.get_rotation()
        except:
            pass

        annot_count = pdfium_c.FPDFPage_GetAnnotCount(page)
        for i in range(annot_count):
            link = {
                'bbox': None,
                'page': page_idx,
                'dest_page': None,
                'dest_pos': None,
                'url': None,
            }
            annot = pdfium_c.FPDFPage_GetAnnot(page, i)
            if pdfium_c.FPDFAnnot_GetSubtype(annot) == pdfium_c.FPDF_ANNOT_LINK:
                fs_rect = pdfium_c.FS_RECTF()
                success = pdfium_c.FPDFAnnot_GetRect(annot, ctypes.byref(fs_rect))
                if not success:
                    continue
                link['bbox'] = self.rect_to_scaled_bbox(
                    [fs_rect.left, fs_rect.top, fs_rect.right, fs_rect.bottom],
                    page_bbox, page_height, page_width, page_rotation
                )

                link_obj = pdfium_c.FPDFAnnot_GetLink(annot)

                dest = pdfium_c.FPDFLink_GetDest(self.doc, link_obj)
                if dest:
                    tgt_page = pdfium_c.FPDFDest_GetDestPageIndex(self.doc, dest)
                    link['dest_page'] = tgt_page
                    dest_position = self.get_dest_position(dest)
                    if dest_position:
                        link['dest_pos'] = self.xy_to_scaled_pos(*dest_position, page_bbox, page_height, page_width, page_rotation)

                else:
                    action = pdfium_c.FPDFLink_GetAction(link_obj)
                    a_type = pdfium_c.FPDFAction_GetType(action)

                    if a_type == pdfium_c.PDFACTION_UNSUPPORTED:
                        continue

                    elif a_type == pdfium_c.PDFACTION_GOTO:
                        # Goto a page
                        dest = pdfium_c.FPDFAction_GetDest(self.doc, action)
                        if dest:
                            tgt_page = pdfium_c.FPDFDest_GetDestPageIndex(self.doc, dest)
                            link['dest_page'] = tgt_page
                            dest_position = self.get_dest_position(dest)
                            if dest_position:
                                link['dest_pos'] = self.xy_to_scaled_pos(*dest_position, page_bbox, page_height, page_width, page_rotation)

                    elif a_type == pdfium_c.PDFACTION_URI:
                        # External link
                        needed_len = pdfium_c.FPDFAction_GetURIPath(self.doc, action, None, 0)
                        if needed_len > 0:
                            buf = ctypes.create_string_buffer(needed_len)
                            pdfium_c.FPDFAction_GetURIPath(self.doc, action, buf, needed_len)
                            uri = buf.raw[:needed_len].decode('utf-8', errors='replace').rstrip('\x00')
                            link["url"] = uri

                urls.append(link)
        return urls
