import os

from marker.settings import settings

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # Transformers uses .isin for a simple op, which is not supported on MPS

from typing import List
from PIL import Image

from surya.detection import DetectionPredictor
from surya.layout import LayoutPredictor
from surya.ocr_error import OCRErrorPredictor
from surya.recognition import RecognitionPredictor
from surya.table_rec import TableRecPredictor

from texify.model.model import load_model as load_texify_model
from texify.model.processor import load_processor as load_texify_processor
from texify.inference import batch_inference

class TexifyPredictor:
    def __init__(self, device=None, dtype=None):
        if not device:
            device = settings.TORCH_DEVICE_MODEL
        if not dtype:
            dtype = settings.TEXIFY_DTYPE

        self.model = load_texify_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=device, dtype=dtype)
        self.processor = load_texify_processor()
        self.device = device
        self.dtype = dtype

    def __call__(self, batch_images: List[Image.Image], max_tokens: int):
        return batch_inference(
            batch_images,
            self.model,
            self.processor,
            max_tokens=max_tokens
        )


def create_model_dict(device=None, dtype=None) -> dict:
    return {
        "layout_model": LayoutPredictor(device=device, dtype=dtype),
        "texify_model": TexifyPredictor(device=device, dtype=dtype),
        "recognition_model": RecognitionPredictor(device=device, dtype=dtype),
        "table_rec_model": TableRecPredictor(device=device, dtype=dtype),
        "detection_model": DetectionPredictor(device=device, dtype=dtype),
        "ocr_error_model": OCRErrorPredictor(device=device, dtype=dtype)
    }