import os
from PIL import Image
from io import BytesIO
import base64
import os
from typing import Tuple, List, Optional

from spellchecker import SpellChecker

from marker.bbox import correct_rotation
from marker.ocr.page import ocr_entire_page
from marker.ocr.utils import detect_bad_ocr, font_flags_decomposer
from marker.settings import settings
from marker.schema import Span, Line, Block, Page
from concurrent.futures import ThreadPoolExecutor

# IMAGE_LABEL_TEMP_MD = '![{}]({})'

os.environ["TESSDATA_PREFIX"] = settings.TESSDATA_PREFIX


def sort_rotated_text(page_blocks, tolerance=1.25):
    vertical_groups = {}
    for block in page_blocks:
        group_key = round(block.bbox[1] / tolerance) * tolerance
        if group_key not in vertical_groups:
            vertical_groups[group_key] = []
        vertical_groups[group_key].append(block)

    # Sort each group horizontally and flatten the groups into a single list
    sorted_page_blocks = []
    for _, group in sorted(vertical_groups.items()):
        sorted_group = sorted(group, key=lambda x: x.bbox[0])
        sorted_page_blocks.extend(sorted_group)

    return sorted_page_blocks


def get_single_page_blocks(doc, pnum: int, tess_lang: str, spellchecker: Optional[SpellChecker] = None, ocr=False) -> Tuple[List[Block], int]:
    page = doc[pnum]
    if ocr:
        blocks = ocr_entire_page(page, tess_lang, spellchecker)
    else:
        blocks = page.get_text("dict", sort=True, flags=settings.TEXT_FLAGS)["blocks"]

    page_blocks = []
    img_meta = {}
    span_id = 0
    for block_idx, block in enumerate(blocks):
        block_lines = []
        for l in block["lines"]:
            spans = []
            for i, s in enumerate(l["spans"]):
                block_text = s["text"]
                bbox = s["bbox"]
                span_obj = Span(
                    text=block_text,
                    bbox=correct_rotation(bbox, page),
                    span_id=f"{pnum}_{span_id}",
                    font=f"{s['font']}_{font_flags_decomposer(s['flags'])}", # Add font flags to end of font
                    color=s["color"],
                    ascender=s["ascender"],
                    descender=s["descender"],
                )
                spans.append(span_obj)  # Text, bounding box, span id
                span_id += 1
            line_obj = Line(
                spans=spans,
                bbox=correct_rotation(l["bbox"], page),
            )
            # Only select valid lines, with positive bboxes
            if line_obj.area > 0:
                block_lines.append(line_obj)
        block_obj = Block(
            lines=block_lines,
            bbox=correct_rotation(block["bbox"], page),
            pnum=pnum
        )
        # Only select blocks with multiple lines
        if len(block_lines) > 0:
            page_blocks.append(block_obj)
    
    # adding image label
    img_list = page.get_images(full=True)
    pics_folder = settings.IMG_SAVE_POSITION
    img_rename_tmpl = settings.IMAGE_LABEL_TEMP_MD

    for img_data in img_list:
        # print(img_data)
        xref = img_data[0]
        img = doc.extract_image(xref)
        img_name = f"IM{xref}.{img['ext']}"
        # print(len(img))
        img_bbox = page.get_image_bbox(img_data)
        
        # save image
        img = doc.extract_image(xref)
        # bytes_io = BytesIO(img["image"])
        img_byte_base64_encoded =base64.b64encode(img["image"]).decode('utf-8')
        # image = Image.open(bytes_io)
        img_meta[img_name] = img_byte_base64_encoded
        img_save_path = os.path.join(pics_folder, img_name)
        # image.save(img_save_path)
        img_label_text = img_rename_tmpl.format(img_name, img_save_path)
        # print(img_label_text)
        img_span = Span(
            # text=IMAGE_LABEL_TEMP.format(img_name),
            text = img_label_text,
            bbox=img_bbox,
            span_id=f"{pnum}_{span_id}",
            font=f"{s['font']}_{font_flags_decomposer(s['flags'])}",  # Add font flags to end of font
            color=0,
            ascender=0.89111328125,
            descender=-0.21630859375,
        )
        
        line_obj = Line(
            spans=[img_span],
            bbox=img_bbox
        )
        block_obj = Block(
            lines=[line_obj], bbox=img_bbox, pnum=pnum
        )
        # print(block_obj)
        page_blocks.append(block_obj)
        span_id += 1
    page_blocks.sort(key=lambda x: x.bbox[1])
    return page_blocks, img_meta


def convert_single_page(doc, pnum, tess_lang: str, spell_lang: Optional[str], no_text: bool, disable_ocr: bool = False, min_ocr_page: int = 2):
    ocr_pages = 0
    ocr_success = 0
    ocr_failed = 0
    spellchecker = None
    page_bbox = doc[pnum].bound()
    if spell_lang:
        spellchecker = SpellChecker(language=spell_lang)

    blocks, img_data = get_single_page_blocks(doc, pnum, tess_lang, spellchecker)
    page_obj = Page(blocks=blocks, pnum=pnum, bbox=page_bbox)

    # OCR page if we got minimal text, or if we got too many spaces
    conditions = [
        (
            no_text  # Full doc has no text, and needs full OCR
            or
            (len(page_obj.prelim_text) > 0 and detect_bad_ocr(page_obj.prelim_text, spellchecker))  # Bad OCR
        ),
        min_ocr_page < pnum < len(doc) - 1,
        not disable_ocr
    ]
    if all(conditions) or settings.OCR_ALL_PAGES:
        blocks, img_data = get_single_page_blocks(doc, pnum, tess_lang, spellchecker, ocr=True)
        page_obj = Page(blocks=blocks, pnum=pnum, bbox=page_bbox)
        ocr_pages = 1
        if len(blocks) == 0:
            ocr_failed = 1
        else:
            ocr_success = 1
    return page_obj, img_data, {"ocr_pages": ocr_pages, "ocr_failed": ocr_failed, "ocr_success": ocr_success}


def get_text_blocks(doc, tess_lang: str, spell_lang: Optional[str], max_pages: Optional[int] = None, parallel: int = settings.OCR_PARALLEL_WORKERS):
    all_blocks = []
    toc = doc.get_toc()
    all_images = {}
    ocr_pages = 0
    ocr_failed = 0
    ocr_success = 0
    # This is a thread because most of the work happens in a separate process (tesseract)
    range_end = len(doc)
    no_text = len(naive_get_text(doc).strip()) == 0
    if max_pages:
        range_end = min(max_pages, len(doc))
    with ThreadPoolExecutor(max_workers=parallel) as pool:
        args_list = [(doc, pnum, tess_lang, spell_lang, no_text) for pnum in range(range_end)]
        if parallel == 1:
            func = map
        else:
            func = pool.map
        results = func(lambda a: convert_single_page(*a), args_list)

        for result in results:
            page_obj, img_data, ocr_stats = result
            all_blocks.append(page_obj)
            all_images.update(img_data)
            ocr_pages += ocr_stats["ocr_pages"]
            ocr_failed += ocr_stats["ocr_failed"]
            ocr_success += ocr_stats["ocr_success"]

    return all_blocks, toc, all_images, {"ocr_pages": ocr_pages, "ocr_failed": ocr_failed, "ocr_success": ocr_success}


def naive_get_text(doc):
    full_text = ""
    for page in doc:
        full_text += page.get_text("text", sort=True, flags=settings.TEXT_FLAGS)
        full_text += "\n"
    return full_text
