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

processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)

CHUNK_KEYS = ["input_ids", "attention_mask", "bbox", "offset_mapping"]
NO_CHUNK_KEYS = ["pixel_values"]
MODEL_MAX_LEN = 512
CHUNK_OVERLAP = 128


def load_model():
    model = LayoutLMv3ForTokenClassification.from_pretrained("Kwan0/layoutlmv3-base-finetune-DocLayNet-100k").to(settings.TORCH_DEVICE)
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

    model.config.label2id = d = {v: k for k, v in model.config.id2label.items()}
    return model


layoutlm_model = load_model()


def detect_all_block_types(doc, blocks: List[Page]):
    block_types = []
    for pnum, page in enumerate(doc):
        page_blocks = blocks[pnum]
        predictions = detect_page_block_types(page, page_blocks)
        block_types.append(predictions)
    return block_types


def detect_page_block_types(page, page_blocks: Page):
    page_box = page.bound()
    pwidth = page_box[2] - page_box[0]
    pheight = page_box[3] - page_box[1]

    pix = page.get_pixmap(dpi=400)
    png = pix.pil_tobytes(format="PNG")
    png_image = Image.open(io.BytesIO(png))
    rgb_image = png_image.convert('RGB')

    lines = page_blocks.get_all_lines()
    boxes = [s.bbox for s in lines]
    text = [s.prelim_text for s in lines]

    predictions = make_predictions(rgb_image, text, boxes, pwidth, pheight)
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


def make_predictions(rgb_image, text, boxes, pwidth, pheight) -> List[BlockType]:
    # Normalize boxes for model (scale to 1000x1000)
    boxes = [normalize_box(box, pwidth, pheight) for box in boxes]
    encoding = processor(rgb_image, text=text, boxes=boxes, return_offsets_mapping=True, return_tensors="pt", truncation=True, stride=CHUNK_OVERLAP, padding="max_length", max_length=MODEL_MAX_LEN, return_overflowing_tokens=True)
    offset_mapping = encoding.pop('offset_mapping')
    overflow_to_sample_mapping = encoding.pop('overflow_to_sample_mapping')

    # change the shape of pixel values
    x = []
    for i in range(0, len(encoding['pixel_values'])):
        x.append(encoding['pixel_values'][i])
    x = torch.stack(x)
    encoding['pixel_values'] = x

    with torch.no_grad():
        encoding = encoding.to(settings.TORCH_DEVICE)
        outputs = layoutlm_model(**encoding)

    logits = outputs.logits
    # We take the highest score for each token, using argmax. This serves as the predicted label for each token.
    predictions = logits.argmax(-1).squeeze().tolist()
    token_boxes = encoding.bbox.squeeze().tolist()

    if len(token_boxes) == MODEL_MAX_LEN:
        predictions = [predictions]
        token_boxes = [token_boxes]

    predicted_block_types = []

    for i, (pred, box, mapped) in enumerate(zip(predictions, token_boxes, offset_mapping)):
        is_subword = np.array(mapped.squeeze().tolist())[:, 0] != 0
        overlap_adjust = 0
        if i > 0:
            overlap_adjust = 1 + CHUNK_OVERLAP - sum(is_subword[:1 + CHUNK_OVERLAP])

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

    return predicted_block_types

