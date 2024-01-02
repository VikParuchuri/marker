from concurrent.futures import ThreadPoolExecutor
from typing import List

from transformers import LayoutLMv3ForTokenClassification

from marker.bbox import unnormalize_box
from transformers.models.layoutlmv3.image_processing_layoutlmv3 import normalize_box
import io
from PIL import Image
from transformers import LayoutLMv3Processor
import numpy as np
from marker.settings import settings
from marker.schema import Page, BlockType
import torch
from math import isclose

# Otherwise some images can be truncated
Image.MAX_IMAGE_PIXELS = None

processor = LayoutLMv3Processor.from_pretrained(settings.LAYOUT_MODEL_NAME, apply_ocr=False)

CHUNK_KEYS = ["input_ids", "attention_mask", "bbox", "offset_mapping"]
NO_CHUNK_KEYS = ["pixel_values"]


def load_layout_model():
    model = LayoutLMv3ForTokenClassification.from_pretrained(
        settings.LAYOUT_MODEL_NAME,
        torch_dtype=settings.MODEL_DTYPE,
    ).to(settings.TORCH_DEVICE_MODEL)

    model.config.id2label = {
        0: "Caption",
        1: "Footnote",
        2: "Formula",
        3: "List-item",
        4: "Page-footer",
        5: "Page-header",
        6: "Picture",
        7: "Section-header",
        8: "Table",
        9: "Text",
        10: "Title"
    }

    model.config.label2id = {v: k for k, v in model.config.id2label.items()}
    return model


def detect_document_block_types(doc, blocks: List[Page], layoutlm_model, batch_size=settings.LAYOUT_BATCH_SIZE):
    encodings, metadata, sample_lengths = get_features(doc, blocks)
    predictions = predict_block_types(encodings, layoutlm_model, batch_size)
    block_types = match_predictions_to_boxes(encodings, predictions, metadata, sample_lengths, layoutlm_model)
    assert len(block_types) == len(blocks)
    return block_types


def get_provisional_boxes(pred, box, is_subword, start_idx=0):
    prov_predictions = [pred_ for idx, pred_ in enumerate(pred) if not is_subword[idx]][start_idx:]
    prov_boxes = [box_ for idx, box_ in enumerate(box) if not is_subword[idx]][start_idx:]
    return prov_predictions, prov_boxes


def get_page_encoding(page, page_blocks: Page):
    if len(page_blocks.get_all_lines()) == 0:
        return [], []

    page_box = page_blocks.bbox
    pwidth = page_blocks.width
    pheight = page_blocks.height

    pix = page.get_pixmap(dpi=settings.LAYOUT_DPI, annots=False, clip=page_blocks.bbox)
    png = pix.pil_tobytes(format="PNG")
    png_image = Image.open(io.BytesIO(png))
    # If it is too large, make it smaller for the model
    rgb_image = png_image.convert('RGB')
    rgb_width, rgb_height = rgb_image.size

    # Image is correct size wrt the pdf page
    assert isclose(rgb_width / pwidth, rgb_height / pheight, abs_tol=2e-2)

    lines = page_blocks.get_all_lines()

    boxes = []
    text = []
    for line in lines:
        box = line.bbox
        # Bounding boxes sometimes overflow
        if box[0] < page_box[0]:
            box[0] = page_box[0]
        if box[1] < page_box[1]:
            box[1] = page_box[1]
        if box[2] > page_box[2]:
            box[2] = page_box[2]
        if box[3] > page_box[3]:
            box[3] = page_box[3]

        # Handle case when boxes are 0 or less width or height
        if box[2] <= box[0]:
            print("Zero width box found, cannot convert properly")
            raise ValueError
        if box[3] <= box[1]:
            print("Zero height box found, cannot convert properly")
            raise ValueError
        boxes.append(box)
        text.append(line.prelim_text)

    # Normalize boxes for model (scale to 1000x1000)
    boxes = [normalize_box(box, pwidth, pheight) for box in boxes]
    for box in boxes:
        # Verify that boxes are all valid
        assert(len(box) == 4)
        assert(max(box)) <= 1000
        assert(min(box)) >= 0

    encoding = processor(
        rgb_image,
        text=text,
        boxes=boxes,
        return_offsets_mapping=True,
        truncation=True,
        return_tensors="pt",
        stride=settings.LAYOUT_CHUNK_OVERLAP,
        padding="max_length",
        max_length=settings.LAYOUT_MODEL_MAX,
        return_overflowing_tokens=True
    )
    offset_mapping = encoding.pop('offset_mapping')
    overflow_to_sample_mapping = encoding.pop('overflow_to_sample_mapping')
    bbox = list(encoding["bbox"])
    input_ids = list(encoding["input_ids"])
    attention_mask = list(encoding["attention_mask"])
    pixel_values = list(encoding["pixel_values"])

    assert len(bbox) == len(input_ids) == len(attention_mask) == len(pixel_values) == len(offset_mapping)

    list_encoding = []
    for i in range(len(bbox)):
        list_encoding.append({
            "bbox": bbox[i],
            "input_ids": input_ids[i],
            "attention_mask": attention_mask[i],
            "pixel_values": pixel_values[i],
            "offset_mapping": offset_mapping[i]
        })

    other_data = {
        "original_bbox": boxes,
        "pwidth": pwidth,
        "pheight": pheight,
    }
    return list_encoding, other_data


def get_features(doc, blocks):
    encodings = []
    metadata = []
    sample_lengths = []
    for i in range(len(blocks)):
        encoding, other_data = get_page_encoding(doc[i], blocks[i])
        encodings.extend(encoding)
        metadata.append(other_data)
        sample_lengths.append(len(encoding))
    return encodings, metadata, sample_lengths


def predict_block_types(encodings, layoutlm_model, batch_size):
    all_predictions = []
    for i in range(0, len(encodings), batch_size):
        batch_start = i
        batch_end = min(i + batch_size, len(encodings))
        batch = encodings[batch_start:batch_end]

        model_in = {}
        for k in ["bbox", "input_ids", "attention_mask", "pixel_values"]:
            model_in[k] = torch.stack([b[k] for b in batch]).to(layoutlm_model.device)

        model_in["pixel_values"] = model_in["pixel_values"].to(layoutlm_model.dtype)

        with torch.inference_mode():
            outputs = layoutlm_model(**model_in)
            logits = outputs.logits

        predictions = logits.argmax(-1).squeeze().tolist()
        if len(predictions) == settings.LAYOUT_MODEL_MAX:
            predictions = [predictions]
        all_predictions.extend(predictions)
    return all_predictions


def match_predictions_to_boxes(encodings, predictions, metadata, sample_lengths, layoutlm_model) -> List[List[BlockType]]:
    assert len(encodings) == len(predictions) == sum(sample_lengths)
    assert len(metadata) == len(sample_lengths)

    page_start = 0
    page_block_types = []
    for pnum, sample_length in enumerate(sample_lengths):
        # Page has no blocks
        if sample_length == 0:
            page_block_types.append([])
            continue

        page_data = metadata[pnum]
        page_end = min(page_start + sample_length, len(predictions))
        page_predictions = predictions[page_start:page_end]
        page_encodings = encodings[page_start:page_end]
        token_boxes = [e["bbox"] for e in page_encodings]
        offset_mapping = [e["offset_mapping"] for e in page_encodings]
        pwidth = page_data["pwidth"]
        pheight = page_data["pheight"]
        boxes = page_data["original_bbox"]

        predicted_block_types = []

        for i in range(len(token_boxes)):
            assert len(token_boxes[i]) == len(page_predictions[i])

        for i, (pred, box, mapped) in enumerate(zip(page_predictions, token_boxes, offset_mapping)):
            box = box.tolist()
            is_subword = np.array(mapped)[:, 0] != 0
            overlap_adjust = 0
            if i > 0:
                overlap_adjust = 1 + settings.LAYOUT_CHUNK_OVERLAP - sum(is_subword[:1 + settings.LAYOUT_CHUNK_OVERLAP])

            prov_predictions, prov_boxes = get_provisional_boxes(pred, box, is_subword, overlap_adjust)

            for prov_box, prov_prediction in zip(prov_boxes, prov_predictions):
                if prov_box == [0, 0, 0, 0]:
                    continue
                block_type = BlockType(
                    block_type=layoutlm_model.config.id2label[prov_prediction],
                    bbox=prov_box
                )

                # Sometimes blocks will cross chunks, unclear why
                if len(predicted_block_types) == 0 or prov_box != predicted_block_types[-1].bbox:
                    predicted_block_types.append(block_type)

        # Align bboxes
        # This will search both lists to find matching bboxes
        # This will align both sets of bboxes by index
        # If there are duplicate bboxes, it may result in issues
        aligned_blocks = []
        for i in range(len(boxes)):
            unnorm_box = unnormalize_box(boxes[i], pwidth, pheight)
            appended = False
            for j in range(len(predicted_block_types)):
                if boxes[i] == predicted_block_types[j].bbox:
                    predicted_block_types[j].bbox = unnorm_box
                    aligned_blocks.append(predicted_block_types[j])
                    appended = True
                    break
            if not appended:
                aligned_blocks.append(BlockType(
                    block_type="Text",
                    bbox=unnorm_box
                ))
        page_block_types.append(aligned_blocks)
        page_start += sample_length
    return page_block_types

