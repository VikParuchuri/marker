import functools
from typing import Dict, List, Optional, Set, Tuple

import pypdfium2 as pdfium
from pdftext.extraction import dictionary_output
from PIL import Image
from pydantic import BaseModel
from surya.detection import batch_text_detection
from surya.ocr import run_recognition

from marker.ocr.heuristics import detect_bad_ocr
from marker.settings import settings
from marker.v2.providers import BaseProvider
from marker.v2.schema.polygon import PolygonBox
from marker.v2.schema.text.line import Line
from marker.v2.schema.text.span import Span

PageLines = Dict[int, List[Line]]
LineSpans = Dict[int, List[Span]]
PageSpans = Dict[int, LineSpans]


class PdfProvider(BaseProvider):
    page_range: List[int] | None = None
    pdftext_workers: int = 4
    flatten_pdf: bool = True

    def __init__(self, filepath: str, detection_model, ocr_model, config: Optional[BaseModel] = None):
        super().__init__(filepath, config)

        self.detection_model = detection_model
        self.ocr_model = ocr_model

        self.page_lines: PageLines = {}
        self.page_spans: PageSpans = {}
        self.doc: pdfium.PdfDocument = pdfium.PdfDocument(self.filepath)

        if self.page_range is None:
            self.page_range = range(len(self.doc))
        assert max(self.page_range) < len(self.doc) and min(self.page_range) >= 0, "Invalid page range"

    def process_document(self):
        pdftext_page_lines, pdftext_page_spans = self.pdftext_extraction()
        detection_page_lines = self.text_detection()
        self.page_lines, merged_page_spans = self.merge_lines(detection_page_lines, pdftext_page_lines, pdftext_page_spans)
        self.page_spans = self.ocr_extraction(merged_page_spans)

    def __len__(self) -> int:
        return len(self.doc)

    def __del__(self):
        if self.doc is not None:
            self.doc.close()

    def text_detection(self) -> PageLines:
        page_lines: PageLines = {}
        page_detection_results = batch_text_detection(
            [self.get_image(i, settings.IMAGE_DPI) for i in self.page_range],
            self.detection_model,
            self.detection_model.processor,
        )
        for page_id, page_detection_result in enumerate(page_detection_results):
            image_size = PolygonBox.from_bbox(page_detection_result.image_bbox).size
            page_size = self.get_page_bbox(page_id).size
            lines: List[Line] = []
            for line in page_detection_result.bboxes:
                polygon = PolygonBox(polygon=line.polygon).rescale(image_size, page_size)
                lines.append(Line(polygon=polygon, page_id=page_id, origin="surya"))
            page_lines[page_id] = lines
        return page_lines

    def ocr_extraction(self, page_spans: PageSpans):
        page_id_list: List[int] = []
        ocr_bbox_page_list: List[List[List[int]]] = []
        ocr_page_line_idx_list: List[List[int]] = []

        for page_id, lines in self.page_lines.items():
            page_size = self.get_page_bbox(page_id).size
            image_size = self.get_image(page_id, settings.IMAGE_DPI).size
            ocr_bbox_list = []
            ocr_line_idx_list = []
            line_spans = page_spans[page_id]
            for line_idx, line in enumerate(lines):
                if not line_spans[line_idx] and line.origin == "surya":
                    ocr_polygon = line.polygon.rescale(page_size, image_size)
                    if ocr_polygon.area > 0:
                        ocr_bbox_list.append(list(map(int, ocr_polygon.bbox)))
                        ocr_line_idx_list.append(line_idx)
            if len(ocr_bbox_list):
                ocr_bbox_page_list.append(ocr_bbox_list)
                ocr_page_line_idx_list.append(ocr_line_idx_list)
                page_id_list.append(page_id)

        recognition_results = run_recognition(
            images=[self.get_image(i, settings.IMAGE_DPI) for i in page_id_list],
            langs=[None] * len(page_id_list),
            rec_model=self.ocr_model,
            rec_processor=self.ocr_model.processor,
            bboxes=ocr_bbox_page_list,
        )

        for (page_id, ocr_page_line_idxs, recognition_result) in zip(page_id_list, ocr_page_line_idx_list, recognition_results):
            line_spans = page_spans[page_id]
            for ocr_line_idx, ocr_line in zip(ocr_page_line_idxs, recognition_result.text_lines):
                line_spans[ocr_line_idx].append(Span(
                    text=ocr_line.text,
                    formats=['plain'],
                    page_id=page_id,
                    polygon=PolygonBox.from_bbox(ocr_line.bbox),
                    minimum_position=0,
                    maximum_position=0,
                    font='',
                    font_weight=0,
                    font_size=0,
                    text_extraction_method="surya"
                ))

        return page_spans

    def merge_lines(
        self,
        detection_page_lines: PageLines,
        pdftext_page_lines: PageLines,
        pdftext_page_spans: PageSpans
    ):
        page_lines: PageLines = {}
        page_spans: PageSpans = {}
        for page_id, (detection_lines, pdftext_lines, pdftext_spans) in enumerate(zip(detection_page_lines.values(), pdftext_page_lines.values(), pdftext_page_spans.values())):
            page_lines[page_id] = []
            line_spans = {}

            # if we don't pass these checks, we don't include any data from pdftext
            if not (self.check_line_coverage(detection_lines, pdftext_lines) and self.check_line_spans(pdftext_spans)):
                page_lines[page_id] = detection_lines
                page_spans[page_id] = {i: [] for i in range(len(detection_lines))}
                continue

            all_lines = []
            for pdftext_idx, pdftext_line in enumerate(pdftext_lines):
                matched = False
                for detection_idx, detection_line in enumerate(detection_lines):
                    if detection_line.polygon.intersection_pct(pdftext_line.polygon) > 0:
                        detection_line.polygon = detection_line.polygon.merge([pdftext_line.polygon])
                        matched = True

                        all_lines.append(detection_line)
                        span_idx = len(all_lines) - 1
                        if span_idx not in line_spans:
                            line_spans[span_idx] = []
                        line_spans[span_idx].extend(pdftext_spans[pdftext_idx])
                        break

                if not matched:
                    all_lines.append(pdftext_line)
                    line_spans[len(all_lines) - 1] = pdftext_spans[pdftext_idx]

            for line_idx in range(len(all_lines)):
                if line_idx not in line_spans:
                    line_spans[line_idx] = []

            page_lines[page_id] = all_lines
            page_spans[page_id] = line_spans

        return page_lines, page_spans

    def font_flags_to_format(self, flags: int) -> Set[str]:
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

    def font_names_to_format(self, font_name: str) -> Set[str]:
        formats = set()
        if "bold" in font_name.lower():
            formats.add("bold")
        if "ital" in font_name.lower():
            formats.add("italic")
        return formats

    def pdftext_extraction(self) -> Tuple[PageLines, PageSpans]:
        page_lines: PageLines = {}
        page_spans: PageSpans = {}
        page_char_blocks = dictionary_output(
            self.filepath,
            page_range=self.page_range,
            keep_chars=False,
            workers=self.pdftext_workers,
            flatten_pdf=self.flatten_pdf
        )
        for page in page_char_blocks:
            page_id = page["page"]
            lines: List[Line] = []
            line_spans: LineSpans = {}
            for block in page["blocks"]:
                for line in block["lines"]:
                    spans: List[Span] = []
                    for span in line["spans"]:
                        if not span["text"].strip():
                            continue
                        font_formats = self.font_flags_to_format(span["font"]["flags"]).union(self.font_names_to_format(span["font"]["name"]))
                        spans.append(
                            Span(
                                polygon=PolygonBox.from_bbox(span["bbox"]),
                                text=span["text"],
                                font=span["font"]["name"],
                                font_weight=span["font"]["weight"],
                                font_size=span["font"]["size"],
                                minimum_position=span["char_start_idx"],
                                maximum_position=span["char_end_idx"],
                                formats=list(font_formats),
                                page_id=page_id,
                                text_extraction_method="pdftext"
                            )
                        )
                    lines.append(Line(polygon=PolygonBox.from_bbox(line["bbox"]), page_id=page_id, origin="pdftext"))
                    line_spans[len(lines) - 1] = spans
            page_lines[page_id] = lines
            page_spans[page_id] = line_spans
        return page_lines, page_spans

    def check_line_spans(self, page_spans: LineSpans) -> bool:
        if not len(sum(list(page_spans.values()), [])):
            return False
        text = ""
        for line_spans in page_spans.values():
            for span in line_spans:
                text = text + " " + span.text
            text = text + "\n"
        if len(text.strip()) == 0:
            return False
        if detect_bad_ocr(text):
            return False
        return True

    def check_line_coverage(
        self,
        detection_lines: List[Line],
        pdftext_lines: List[Line],
        intersection_threshold=0.5,
        detection_threshold=0.4,
        difference_threshold=0.5
    ):
        # If there are no detection lines, we return True as there's nothing to cover
        if not detection_lines:
            return True

        # if there are fewer pdftext lines than detection lines, we return False
        if len(pdftext_lines) < difference_threshold * len(detection_lines):
            return False

        intersecting_lines = 0
        for detected_line in detection_lines:
            for pdftext_line in pdftext_lines:
                intersection_pct = detected_line.polygon.intersection_pct(pdftext_line.polygon)
                if intersection_pct > intersection_threshold:
                    intersecting_lines += 1
                    break  # Move to the next detected line once it's covered

        coverage_ratio = intersecting_lines / len(detection_lines)
        return coverage_ratio >= detection_threshold

    @functools.lru_cache(maxsize=None)
    def get_image(self, idx: int, dpi: int) -> Image.Image:
        page = self.doc[idx]
        image = page.render(scale=dpi / 72, draw_annots=False).to_pil()
        image = image.convert("RGB")
        return image

    def get_page_bbox(self, idx: int) -> PolygonBox:
        page = self.doc[idx]
        return PolygonBox.from_bbox(page.get_bbox())

    def get_page_lines(self, idx: int) -> PageLines:
        return self.page_lines[idx]

    def get_page_spans(self, idx: int) -> PageSpans:
        return self.page_spans[idx]
