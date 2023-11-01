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

processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)

CHUNK_KEYS = ["input_ids", "attention_mask", "bbox", "offset_mapping"]
NO_CHUNK_KEYS = ["pixel_values"]

def load_layout_model():
    model = LayoutLMv3ForTokenClassification.from_pretrained("Kwan0/layoutlmv3-base-finetune-DocLayNet-100k").to(settings.TORCH_DEVICE)
    if settings.CUDA:
        model = model.to(torch.bfloat16)

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


def detect_all_block_types(doc, blocks: List[Page], layoutlm_model):
    block_types = []
    for page_blocks in blocks:
        pnum = page_blocks.pnum
        page = doc[pnum]
        predictions = []
        # Don't make predictions for blank lines
        if len(page_blocks.get_all_lines()) > 0:
            predictions = detect_page_block_types(page, page_blocks, layoutlm_model)
        block_types.append(predictions)
    return block_types


def resize_image(png_image, max_size=8000):
    width, height = png_image.size

    if width > max_size:
        max_size = (max_size, max_size)

        # Resize the image, preserving the aspect ratio
        png_image.thumbnail(max_size, Image.LANCZOS)


def detect_page_block_types(page, page_blocks: Page, layoutlm_model):
    page_box = page.bound()
    pwidth = page_box[2] - page_box[0]
    pheight = page_box[3] - page_box[1]

    pix = page.get_pixmap(dpi=settings.DPI, annots=False, clip=page.bound())
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

    predictions = make_predictions(rgb_image, text, boxes, pwidth, pheight, layoutlm_model)
    return predictions


def find_first_false(lst, start_idx):
    # Traverse the list to the left from start_idx
    for idx in range(start_idx, -1, -1):
        if not lst[idx]:
            return idx

    return 0  # Return 0 if no false found (aka, no lines)


def get_provisional_boxes(pred, box, is_subword, start_idx=0):
    prov_predictions = [pred_ for idx, pred_ in enumerate(pred) if not is_subword[idx]][start_idx:]
    prov_boxes = [box_ for idx, box_ in enumerate(box) if not is_subword[idx]][start_idx:]
    return prov_predictions, prov_boxes


def make_predictions(rgb_image, text, boxes, pwidth, pheight, layoutlm_model) -> List[BlockType]:
    # Normalize boxes for model (scale to 1000x1000)
    boxes = [normalize_box(box, pwidth, pheight) for box in boxes]
    for box in boxes:
        # Verify that boxes are all valid
        assert(len(box) == 4)
        assert(max(box)) <= 1000
        assert(min(box)) >= 0

    encoding = processor(rgb_image, text=text, boxes=boxes, return_offsets_mapping=True, return_tensors="pt", truncation=True, stride=settings.LAYOUT_CHUNK_OVERLAP, padding="max_length", max_length=settings.LAYOUT_MODEL_MAX, return_overflowing_tokens=True)
    offset_mapping = encoding.pop('offset_mapping')
    overflow_to_sample_mapping = encoding.pop('overflow_to_sample_mapping')

    # change the shape of pixel values
    x = []
    for i in range(0, len(encoding['pixel_values'])):
        x.append(encoding['pixel_values'][i])
    x = torch.stack(x)
    encoding['pixel_values'] = x

    if settings.CUDA:
        encoding["pixel_values"] = encoding["pixel_values"].to(torch.bfloat16)

    with torch.no_grad():
        for k in ["bbox", "input_ids", "pixel_values", "attention_mask"]:
            encoding[k] = encoding[k].to(settings.TORCH_DEVICE)
        outputs = layoutlm_model(**encoding)

    logits = outputs.logits
    # We take the highest score for each token, using argmax. This serves as the predicted label for each token.
    predictions = logits.argmax(-1).squeeze().tolist()
    token_boxes = encoding.bbox.squeeze().tolist()

    if len(token_boxes) == settings.LAYOUT_MODEL_MAX:
        predictions = [predictions]
        token_boxes = [token_boxes]

    predicted_block_types = []

    for i, (pred, box, mapped) in enumerate(zip(predictions, token_boxes, offset_mapping)):
        is_subword = np.array(mapped.squeeze().tolist())[:, 0] != 0
        overlap_adjust = 0
        if i > 0:
            overlap_adjust = 1 + settings.LAYOUT_CHUNK_OVERLAP - sum(is_subword[:1 + settings.LAYOUT_CHUNK_OVERLAP])

        prov_predictions, prov_boxes = get_provisional_boxes(pred, box, is_subword, overlap_adjust)

        for prov_box, prov_prediction in zip(prov_boxes, prov_predictions):
            if prov_box == [0, 0, 0, 0]:
                continue
            unnorm_box = unnormalize_box(prov_box, pwidth, pheight)
            block_type = BlockType(
                block_type=layoutlm_model.config.id2label[prov_prediction],
                bbox=unnorm_box
            )

            # Sometimes blocks will cross chunks, unclear why
            if len(predicted_block_types) == 0 or unnorm_box != predicted_block_types[-1].bbox:
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
            if unnorm_box == predicted_block_types[j].bbox:
                aligned_blocks.append(predicted_block_types[j])
                appended = True
                break
        if not appended:
            aligned_blocks.append(BlockType(
                block_type="Text",
                bbox=unnorm_box
            ))
    return aligned_blocks

