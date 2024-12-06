import math
from ctypes import byref, c_int, create_string_buffer

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


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


def get_chars(page, textpage, loose=False):
    chars = []
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


def get_spans(chars):
    spans = []
    for char in chars:
        if not spans or (
            spans and
            any(char['font'][k] != spans[-1]['font'][k] for k in ['name', 'flags', 'size', 'weight'])
        ) or (spans and spans[-1]['text'].endswith("\x02")):
            spans.append({key: char[key] for key in char.keys() if key != 'char_idx'})
        else:
            spans[-1]['text'] += char['text']
            spans[-1]['char_end_idx'] = char['char_end_idx']
            spans[-1]['bbox'] = [
                min(spans[-1]['bbox'][0], char['bbox'][0]),
                min(spans[-1]['bbox'][1], char['bbox'][1]),
                max(spans[-1]['bbox'][2], char['bbox'][2]),
                max(spans[-1]['bbox'][3], char['bbox'][3])
            ]

    return spans


def get_lines(spans):
    lines = []
    current_line = None

    for span in spans:
        if current_line is None:
            current_line = {
                "spans": [span],
                "bbox": span["bbox"],
            }
        else:
            current_line["spans"].append(span)
            current_line["bbox"] = [
                min(current_line["bbox"][0], span["bbox"][0]),
                min(current_line["bbox"][1], span["bbox"][1]),
                max(current_line["bbox"][2], span["bbox"][2]),
                max(current_line["bbox"][3], span["bbox"][3])
            ]

        if span["text"].endswith("\r\n") or span["text"].endswith("\x02"):
            span["text"] = span["text"].replace("\x02", "-")
            lines.append(current_line)
            current_line = None

    if current_line is not None:
        lines.append(current_line)

    return lines


def get_blocks(lines):
    blocks = []
    current_block = None

    for line in lines:
        if current_block is None:
            current_block = {
                "lines": [line],
                "bbox": line["bbox"],
            }
        else:
            current_block["lines"].append(line)
            current_block["bbox"] = [
                min(current_block["bbox"][0], line["bbox"][0]),
                min(current_block["bbox"][1], line["bbox"][1]),
                max(current_block["bbox"][2], line["bbox"][2]),
                max(current_block["bbox"][3], line["bbox"][3])
            ]

    if current_block is not None:
        blocks.append(current_block)

    return blocks


def get_pages(pdf: pdfium.PdfDocument, page_range: range, flatten_pdf: bool = True):
    pages = []
    for page_idx in page_range:
        page = pdf.get_page(page_idx)
        if flatten_pdf:
            flatten(page)
            page = pdf.get_page(page_idx)

        textpage = page.get_textpage()

        page_bbox = page.get_bbox()
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
    pdf_path = '/home/ubuntu/surya-test/pdfs/nested-lists.pdf'
    pdf = pdfium.PdfDocument(pdf_path)

    for page_idx in range(len(pdf)):
        page = pdf.get_page(page_idx)
        textpage = page.get_textpage()

        page_bbox = page.get_bbox()
        page_width = math.ceil(abs(page_bbox[2] - page_bbox[0]))
        page_height = math.ceil(abs(page_bbox[1] - page_bbox[3]))

        chars = get_chars(textpage, page_width, page_height)
        spans = get_spans(chars)
        lines = get_lines(spans)
        blocks = get_blocks(lines)

        for block in blocks:
            for line_idx, line in enumerate(block["lines"]):
                text = ""
                for span_idx, span in enumerate(line["spans"]):
                    text += span["text"]
                print(text, [span["text"] for span in line["spans"]])
