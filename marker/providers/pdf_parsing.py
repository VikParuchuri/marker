import math
from ctypes import byref, c_int, create_string_buffer
from typing import Any, Dict, List, TypedDict, Union

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

from marker.schema.polygon import PolygonBox


class Char(TypedDict):
    bbox: PolygonBox
    text: str
    rotation: float
    font: Dict[str, Union[Any, str]]
    char_idx: int
    char_start_idx: int
    char_end_idx: int


class Span(TypedDict):
    bbox: PolygonBox
    text: str
    font: Dict[str, Union[Any, str]]
    font_weight: float
    font_size: float
    chars: List[Char]


class Line(TypedDict):
    spans: List[Span]
    bbox: PolygonBox


class Block(TypedDict):
    lines: List[Line]
    bbox: PolygonBox


class Page(TypedDict):
    page: int
    bbox: PolygonBox
    width: int
    height: int
    blocks: List[Block]


Chars = List[Char]
Spans = List[Span]
Lines = List[Line]
Blocks = List[Block]
Pages = List[Page]


def flatten(page, flag=pdfium_c.FLAT_NORMALDISPLAY):
    rc = pdfium_c.FPDFPage_Flatten(page, flag)
    if rc == pdfium_c.FLATTEN_FAIL:
        raise pdfium.PdfiumError("Failed to flatten annotations / form fields.")


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


def get_chars(page, textpage, loose=False) -> Chars:
    chars: Chars = []
    start_idx = 0
    end_idx = 1

    x_start, y_start, x_end, y_end = page.get_bbox()
    page_width = math.ceil(abs(x_end - x_start))
    page_height = math.ceil(abs(y_end - y_start))

    for i in range(textpage.count_chars()):
        fontname, fontflag = get_fontname(textpage, i)
        text = chr(pdfium_c.FPDFText_GetUnicode(textpage, i))
        end_idx = start_idx + len(text)

        char_box = textpage.get_charbox(i, loose=loose)
        cx_start, cy_start, cx_end, cy_end = char_box

        cx_start -= x_start
        cx_end -= x_start
        cy_start -= y_start
        cy_end -= y_start

        ty_start = page_height - cy_start
        ty_end = page_height - cy_end

        bbox = [round(cx_start, 2), round(min(ty_start, ty_end), 2), round(cx_end, 2), round(max(ty_start, ty_end), 2)]
        bbox = PolygonBox.from_bbox(bbox)

        chars.append({
            "bbox": bbox,
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


def get_spans(chars: Chars) -> Spans:
    spans: Spans = []
    span: Span = None

    for char in chars:
        if spans:
            span = spans[-1]

        if not span:
            spans.append({key: char[key] for key in char.keys() if key != 'char_idx'} | {"chars": [char]})
        elif (
            any(char['font'][k] != span['font'][k] for k in ['name', 'flags', 'size', 'weight'])
            or span['text'].endswith("\x02")
        ):
            spans.append({key: char[key] for key in char.keys() if key != 'char_idx'} | {"chars": [char]})
        else:
            span['text'] += char['text']
            span['char_end_idx'] = char['char_end_idx']
            span['bbox'] = span['bbox'].merge([char['bbox']])
            span['chars'].append(char)

    return spans


def get_lines(spans: Spans) -> Lines:
    lines: Lines = []
    line: Line = None

    for span in spans:
        if lines:
            line = lines[-1]

        if not line:
            lines.append({
                "spans": [span],
                "bbox": span["bbox"],
            })
        elif any(line["spans"][-1]["text"].endswith(suffix) for suffix in ["\r\n", "\x02"]):
            line["spans"][-1]["text"] = line["spans"][-1]["text"].replace("\x02", "-")
            lines.append({
                "spans": [span],
                "bbox": span["bbox"],
            })
        elif span["bbox"].y_start > line["bbox"].y_end:
            lines.append({
                "spans": [span],
                "bbox": span["bbox"],
            })
        else:
            line["spans"].append(span)
            line["bbox"] = line["bbox"].merge([span["bbox"]])

    return lines


def get_blocks(lines: Lines) -> Blocks:
    blocks: Blocks = []
    block: Block = None

    for line in lines:
        if blocks:
            block = blocks[-1]

        if not block:
            blocks.append({
                "lines": [line],
                "bbox": line["bbox"],
            })
        else:
            block["lines"].append(line)
            block["bbox"] = block["bbox"].merge([line["bbox"]])

    return blocks


def get_pages(pdf: pdfium.PdfDocument, page_range: range, flatten_pdf: bool = True) -> Pages:
    pages: Pages = []

    for page_idx in page_range:
        page = pdf.get_page(page_idx)
        if flatten_pdf:
            flatten(page)
            page = pdf.get_page(page_idx)

        textpage = page.get_textpage()

        page_bbox: List[float] = page.get_bbox()
        page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
        page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

        chars = get_chars(page, textpage)
        spans = get_spans(chars)
        lines = get_lines(spans)
        blocks = get_blocks(lines)

        pages.append({
            "page": page_idx,
            "bbox": page_bbox,
            "width": page_width,
            "height": page_height,
            "blocks": blocks
        })
    return pages


if __name__ == "__main__":
    pdf_path = '/home/ubuntu/surya-test/pdfs/chinese_progit.pdf'
    pdf = pdfium.PdfDocument(pdf_path)

    for page in get_pages(pdf, [481]):
        for block in page["blocks"]:
            for line_idx, line in enumerate(block["lines"]):
                text = ""
                for span_idx, span in enumerate(line["spans"]):
                    text += span["text"]
                print(text, [span["text"] for span in line["spans"]])
