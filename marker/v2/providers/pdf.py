import atexit
import functools
from typing import List, Set

import pypdfium2 as pdfium
from pdftext.extraction import dictionary_output
from PIL import Image

from marker.ocr.heuristics import detect_bad_ocr
from marker.v2.providers import BaseProvider, ProviderOutput, ProviderPageLines
from marker.v2.schema.polygon import PolygonBox
from marker.v2.schema import BlockTypes
from marker.v2.schema.registry import get_block_class
from marker.v2.schema.text.line import Line
from marker.v2.schema.text.span import Span


class PdfProvider(BaseProvider):
    page_range: List[int] | None = None
    pdftext_workers: int = 4
    flatten_pdf: bool = True
    force_ocr: bool = False

    def __init__(self, filepath: str, config=None):
        super().__init__(filepath, config)

        self.doc: pdfium.PdfDocument = pdfium.PdfDocument(self.filepath)
        self.page_lines: ProviderPageLines = {i: [] for i in range(len(self.doc))}

        if self.page_range is None:
            self.page_range = range(len(self.doc))
        assert max(self.page_range) < len(self.doc) and min(self.page_range) >= 0, "Invalid page range"

        if not self.force_ocr:
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
            flatten_pdf=self.flatten_pdf
        )
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
                        spans.append(
                            SpanClass(
                                polygon=PolygonBox.from_bbox(span["bbox"]),
                                text=span["text"],
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
                    lines.append(
                        ProviderOutput(
                            line=LineClass(polygon=PolygonBox.from_bbox(line["bbox"]), page_id=page_id),
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
        if detect_bad_ocr(text):
            return False
        return True

    @functools.lru_cache(maxsize=None)
    def get_image(self, idx: int, dpi: int) -> Image.Image:
        page = self.doc[idx]
        image = page.render(scale=dpi / 72, draw_annots=False).to_pil()
        image = image.convert("RGB")
        return image

    def get_page_bbox(self, idx: int) -> PolygonBox:
        page = self.doc[idx]
        return PolygonBox.from_bbox(page.get_bbox())

    def get_page_lines(self, idx: int) -> List[ProviderOutput]:
        return self.page_lines[idx]