import atexit
import re
from typing import List, Set

import pypdfium2 as pdfium
from ftfy import fix_text
from pdftext.extraction import dictionary_output
from PIL import Image

from marker.providers.utils import alphanum_ratio
from marker.providers import BaseProvider, ProviderOutput, ProviderPageLines
from marker.schema.polygon import PolygonBox
from marker.schema import BlockTypes
from marker.schema.registry import get_block_class
from marker.schema.text.line import Line
from marker.schema.text.span import Span


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
        page_char_blocks = dictionary_output(
            self.filepath,
            page_range=self.page_range,
            keep_chars=False,
            workers=self.pdftext_workers,
            flatten_pdf=self.flatten_pdf,
            quote_loosebox=False
        )
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
                                text=fix_text(span["text"]),
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
