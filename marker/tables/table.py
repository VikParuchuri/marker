from tqdm import tqdm
from pypdfium2 import PdfDocument
from tabled.assignment import assign_rows_columns
from tabled.formats import formatter
from tabled.inference.detection import merge_tables

from surya.input.pdflines import get_page_text_lines
from tabled.inference.recognition import get_cells, recognize_tables

from marker.pdf.images import render_image
from marker.schema.bbox import rescale_bbox
from marker.schema.block import Line, Span, Block
from marker.schema.page import Page
from typing import List
from marker.ocr.recognition import get_batch_size as get_ocr_batch_size
from marker.ocr.detection import get_batch_size as get_detector_batch_size

from marker.settings import settings


def get_batch_size():
    if settings.TABLE_REC_BATCH_SIZE is not None:
        return settings.TABLE_REC_BATCH_SIZE
    elif settings.TORCH_DEVICE_MODEL == "cuda":
        return 6
    return 6


def get_table_boxes(pages: List[Page], doc: PdfDocument, fname):
    table_imgs = []
    table_counts = []
    table_bboxes = []
    img_sizes = []
    pnums = []

    for page_idx, page in enumerate(pages):
        # The bbox for the entire table
        bbox = [b.bbox for b in page.layout.bboxes if b.label == "Table"]
        highres_img = render_image(doc[page_idx], dpi=settings.SURYA_TABLE_DPI)

        page_table_imgs = []
        page_bboxes = []

        # Merge tables that are next to each other
        bbox = merge_tables(bbox)
        bbox = list(filter(lambda b: b[3] - b[1] > 10 and b[2] - b[0] > 10, bbox))

        if len(bbox) == 0:
            table_counts.append(0)
            img_sizes.append(None)
            pnums.append(page.pnum)
            continue

        # Number of tables per page
        table_counts.append(len(bbox))
        img_sizes.append(highres_img.size)
        pnums.append(page.pnum)

        for bb in bbox:
            highres_bb = rescale_bbox(page.layout.image_bbox, [0, 0, highres_img.size[0], highres_img.size[1]], bb)
            page_table_imgs.append(highres_img.crop(highres_bb))
            page_bboxes.append(highres_bb)

        table_imgs.extend(page_table_imgs)
        table_bboxes.extend(page_bboxes)

    # The page number in doc and in the original document are not the same
    # Doc has had pages removed from the start to align to start_page
    # This corrects for that
    doc_idxs = [pnum for pnum, tc in zip(pnums, table_counts) if tc > 0]
    table_idxs = [i for i, tc in enumerate(table_counts) if tc > 0]
    sel_text_lines = get_page_text_lines(
        fname,
        doc_idxs,
        [hr for i, hr in enumerate(img_sizes) if i in table_idxs],
    )
    text_lines = []
    out_img_sizes = []
    for i in range(len(table_counts)):
        if i in table_idxs:
            page_ocred = pages[i].ocr_method is not None
            if page_ocred:
                # This will force re-detection of cells if the page was ocred (the text lines are not accurate)
                text_lines.extend([None] * table_counts[i])
            else:
                text_lines.extend([sel_text_lines.pop(0)] * table_counts[i])
            out_img_sizes.extend([img_sizes[i]] * table_counts[i])

    assert len(table_imgs) == len(table_bboxes) == len(text_lines) == len(out_img_sizes)
    assert sum(table_counts) == len(table_imgs)

    return table_imgs, table_bboxes, table_counts, text_lines, out_img_sizes


def format_tables(pages: List[Page], doc: PdfDocument, fname: str, detection_model, table_rec_model, ocr_model):
    det_models = [detection_model, detection_model.processor]
    rec_models = [table_rec_model, table_rec_model.processor, ocr_model, ocr_model.processor]

    # Don't look at table cell detection tqdm output
    tqdm.disable = True
    table_imgs, table_boxes, table_counts, table_text_lines, img_sizes = get_table_boxes(pages, doc, fname)
    cells, needs_ocr = get_cells(table_imgs, table_boxes, img_sizes, table_text_lines, det_models, detect_boxes=settings.OCR_ALL_PAGES, detector_batch_size=get_detector_batch_size())
    tqdm.disable = False

    # This will redo OCR if OCR is forced, since we need to redetect bounding boxes, etc.
    table_rec = recognize_tables(table_imgs, cells, needs_ocr, rec_models, table_rec_batch_size=get_batch_size(), ocr_batch_size=get_ocr_batch_size())
    cells = [assign_rows_columns(tr, im_size) for tr, im_size in zip(table_rec, img_sizes)]
    table_md = [formatter("markdown", cell)[0] for cell in cells]

    table_count = 0
    for page_idx, page in enumerate(pages):
        page_table_count = table_counts[page_idx]
        if page_table_count == 0:
            continue

        table_insert_points = {}
        blocks_to_remove = set()
        pnum = page.pnum
        highres_size = img_sizes[table_count]
        page_table_boxes = table_boxes[table_count:table_count + page_table_count]

        for table_idx, table_box in enumerate(page_table_boxes):
            lowres_table_box = rescale_bbox([0, 0, highres_size[0], highres_size[1]], page.bbox, table_box)

            for block_idx, block in enumerate(page.blocks):
                intersect_pct = block.intersection_pct(lowres_table_box)
                if intersect_pct > settings.TABLE_INTERSECTION_THRESH and block.block_type == "Table":
                    if table_idx not in table_insert_points:
                        table_insert_points[table_idx] = max(0, block_idx - len(blocks_to_remove)) # Where to insert the new table
                    blocks_to_remove.add(block_idx)

        new_page_blocks = []
        for block_idx, block in enumerate(page.blocks):
            if block_idx in blocks_to_remove:
                continue
            new_page_blocks.append(block)

        for table_idx, table_box in enumerate(page_table_boxes):
            if table_idx not in table_insert_points:
                table_count += 1
                continue

            markdown = table_md[table_count]
            table_block = Block(
                bbox=table_box,
                block_type="Table",
                pnum=pnum,
                lines=[Line(
                    bbox=table_box,
                    spans=[Span(
                        bbox=table_box,
                        span_id=f"{table_idx}_table",
                        font="Table",
                        font_size=0,
                        font_weight=0,
                        block_type="Table",
                        text=markdown
                    )]
                )]
            )
            insert_point = table_insert_points[table_idx]
            insert_point = min(insert_point, len(new_page_blocks))
            new_page_blocks.insert(insert_point, table_block)
            table_count += 1
        page.blocks = new_page_blocks
    return table_count