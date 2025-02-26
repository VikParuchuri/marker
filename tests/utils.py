from typing import Callable
import marker.providers
from marker.providers.pdf import PdfProvider
from marker.schema.polygon import PolygonBox
from marker.schema.text.span import Span
from marker.schema.text.line import Line
import tempfile

import datasets

import pdftext.schema


def setup_pdf_provider(
    filename='adversarial.pdf',
    config=None,
) -> PdfProvider:
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    provider = PdfProvider(temp_pdf.name, config)
    return provider


def convert_to_pdftext(
    word_bboxes: list[tuple[float, float, float, float, str]],
    page_bbox: tuple,
    page_number: int,
):
    """Converts word bboxes (xmin, ymin, xmax, ymax, text) into a pdftext Page object"""
    blocks = []
    block_lines = []

    for x0, y0, x1, y1, text in word_bboxes:
        word_bbox = pdftext.schema.Bbox(bbox=[x0, y0, x1, y1])

        # Create Char entries (assuming each character has uniform bbox)
        chars = []
        char_width = (x1 - x0) / len(text)
        for i, char in enumerate(text):
            char_bbox = pdftext.schema.Bbox(
                bbox=[x0 + i * char_width, y0, x0 + (i + 1) * char_width, y1]
            )
            chars.append(
                pdftext.schema.Char(
                    bbox=char_bbox,
                    char=char,
                    rotation=0,
                    font={"name": "DefaultFont"},
                    char_idx=i,
                )
            )

        span = pdftext.schema.Span(
            bbox=word_bbox,
            text=text,
            font={"name": "DefaultFont"},
            chars=chars,
            char_start_idx=0,
            char_end_idx=len(text) - 1,
            rotation=0,
            url="",
        )

        line = pdftext.schema.Line(spans=[span], bbox=word_bbox, rotation=0)

        block_lines.append(line)

    block = pdftext.schema.Block(lines=block_lines, bbox=page_bbox, rotation=0)
    blocks.append(block)

    page = pdftext.schema.Page(
        page=page_number,
        bbox=page_bbox,
        width=page_bbox[2] - page_bbox[0],
        height=page_bbox[3] - page_bbox[1],
        blocks=blocks,
        rotation=0,
        refs=[],
    )

    return page


_block_counter = 0


def convert_to_provider_output(
    word_bboxes: list[tuple[float, float, float, float, str]],
    page_bbox: tuple,
    get_counter: Callable[[], int] = None,
    page_number: int = 0,
    populate_chars=False,
):
    """Converts word bboxes (xmin, ymin, xmax, ymax, text) into a marker.providers.ProviderOutput object"""

    if get_counter is None:

        def get_counter():
            global _block_counter
            o = _block_counter
            _block_counter += 1
            return o

    all_spans = []
    all_chars = []
    min_x = page_bbox[2]
    max_x = page_bbox[0]
    min_y = page_bbox[3]
    max_y = page_bbox[1]
    for x0, y0, x1, y1, text in word_bboxes:
        word_bbox = PolygonBox.from_bbox([x0, y0, x1, y1])

        # Create Char entries (assuming each character has uniform bbox)
        if populate_chars:
            chars = []
            char_width = (x1 - x0) / len(text)
            for i, char in enumerate(text):
                char_bbox = PolygonBox.from_bbox(
                    [x0 + i * char_width, y0, x0 + (i + 1) * char_width, y1]
                )
                chars.append(
                    marker.providers.Char(char=char, polygon=char_bbox, char_idx=i)
                )

        span = Span(
            polygon=word_bbox,
            text=text,
            font="DefaultFont",
            font_weight=1.0,
            font_size=12.0,
            minimum_position=0,
            maximum_position=len(text) - 1,
            formats=["plain"],
            page_id=page_number,
            block_id=get_counter(),
        )
        all_spans.append(span)
        if populate_chars:
            all_chars.append(chars)

        min_x = min(min_x, x0)
        max_x = max(max_x, x1)
        min_y = min(min_y, y0)
        max_y = max(max_y, y1)

    # line is union of bboxes
    line = Line(
        spans=[span],
        polygon=PolygonBox.from_bbox([min_x, min_y, max_x, max_y]),
        page_id=page_number,
        block_id=get_counter(),
    )

    return marker.providers.ProviderOutput(
        line=line, spans=all_spans, chars=all_chars if populate_chars else None
    )
