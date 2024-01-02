from copy import deepcopy
from typing import List

import torch
import sys, os

from marker.extract_text import convert_single_page
from transformers import LayoutLMv3ForSequenceClassification, LayoutLMv3Processor
from PIL import Image
import io

from marker.schema import Page
from marker.settings import settings

processor = LayoutLMv3Processor.from_pretrained(settings.ORDERER_MODEL_NAME)


def load_ordering_model():
    model = LayoutLMv3ForSequenceClassification.from_pretrained(
        settings.ORDERER_MODEL_NAME,
        torch_dtype=settings.MODEL_DTYPE,
    ).to(settings.TORCH_DEVICE_MODEL)
    model.eval()
    return model


def get_inference_data(page, page_blocks: Page):
    bboxes = deepcopy([block.bbox for block in page_blocks.blocks])
    words = ["."] * len(bboxes)

    pix = page.get_pixmap(dpi=settings.LAYOUT_DPI, annots=False, clip=page_blocks.bbox)
    png = pix.pil_tobytes(format="PNG")
    rgb_image = Image.open(io.BytesIO(png)).convert("RGB")

    page_box = page_blocks.bbox
    pwidth = page_blocks.width
    pheight = page_blocks.height

    for box in bboxes:
        if box[0] < page_box[0]:
            box[0] = page_box[0]
        if box[1] < page_box[1]:
            box[1] = page_box[1]
        if box[2] > page_box[2]:
            box[2] = page_box[2]
        if box[3] > page_box[3]:
            box[3] = page_box[3]

        box[0] = int(box[0] / pwidth * 1000)
        box[1] = int(box[1] / pheight * 1000)
        box[2] = int(box[2] / pwidth * 1000)
        box[3] = int(box[3] / pheight * 1000)

    return rgb_image, bboxes, words


def batch_inference(rgb_images, bboxes, words, model):
    encoding = processor(
        rgb_images,
        text=words,
        boxes=bboxes,
        return_tensors="pt",
        truncation=True,
        padding="max_length",
        max_length=128
    )

    encoding["pixel_values"] = encoding["pixel_values"].to(model.dtype)

    with torch.inference_mode():
        for k in ["bbox", "input_ids", "pixel_values", "attention_mask"]:
            encoding[k] = encoding[k].to(model.device)
        outputs = model(**encoding)
        logits = outputs.logits

    predictions = logits.argmax(-1).squeeze().tolist()
    if isinstance(predictions, int):
        predictions = [predictions]
    predictions = [model.config.id2label[p] for p in predictions]
    return predictions


def add_column_counts(doc, doc_blocks, model, batch_size):
    for i in range(0, len(doc_blocks), batch_size):
        batch = range(i, min(i + batch_size, len(doc_blocks)))
        rgb_images = []
        bboxes = []
        words = []
        for pnum in batch:
            page = doc[pnum]
            rgb_image, page_bboxes, page_words = get_inference_data(page, doc_blocks[pnum])
            rgb_images.append(rgb_image)
            bboxes.append(page_bboxes)
            words.append(page_words)

        predictions = batch_inference(rgb_images, bboxes, words, model)
        for pnum, prediction in zip(batch, predictions):
            doc_blocks[pnum].column_count = prediction


def order_blocks(doc, doc_blocks: List[Page], model, batch_size=settings.ORDERER_BATCH_SIZE):
    add_column_counts(doc, doc_blocks, model, batch_size)

    for page_blocks in doc_blocks:
        if page_blocks.column_count > 1:
            # Resort blocks based on position
            split_pos = page_blocks.x_start + page_blocks.width / 2
            left_blocks = []
            right_blocks = []
            for block in page_blocks.blocks:
                if block.x_start <= split_pos:
                    left_blocks.append(block)
                else:
                    right_blocks.append(block)
            page_blocks.blocks = left_blocks + right_blocks
    return doc_blocks



