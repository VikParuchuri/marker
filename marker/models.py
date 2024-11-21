import os

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # Transformers uses .isin for a simple op, which is not supported on MPS

from surya.model.detection.model import load_model as load_detection_model, load_processor as load_detection_processor
from surya.model.layout.model import load_model as load_layout_model
from surya.model.layout.processor import load_processor as load_layout_processor
from texify.model.model import load_model as load_texify_model
from texify.model.processor import load_processor as load_texify_processor
from marker.settings import settings
from surya.model.recognition.model import load_model as load_recognition_model
from surya.model.recognition.processor import load_processor as load_recognition_processor
from surya.model.table_rec.model import load_model as load_table_model
from surya.model.table_rec.processor import load_processor as load_table_processor

from texify.model.model import GenerateVisionEncoderDecoderModel
from surya.model.layout.encoderdecoder import SuryaLayoutModel
from surya.model.detection.model import EfficientViTForSemanticSegmentation
from surya.model.recognition.encoderdecoder import OCREncoderDecoderModel
from surya.model.table_rec.encoderdecoder import TableRecEncoderDecoderModel


def setup_table_rec_model(device=None, dtype=None) -> TableRecEncoderDecoderModel:
    if device:
        table_model = load_table_model(device=device, dtype=dtype)
    else:
        table_model = load_table_model()
    table_model.processor = load_table_processor()
    return table_model


def setup_recognition_model(device=None, dtype=None) -> OCREncoderDecoderModel:
    if device:
        rec_model = load_recognition_model(device=device, dtype=dtype)
    else:
        rec_model = load_recognition_model()
    rec_model.processor = load_recognition_processor()
    return rec_model


def setup_detection_model(device=None, dtype=None) -> EfficientViTForSemanticSegmentation:
    if device:
        model = load_detection_model(device=device, dtype=dtype)
    else:
        model = load_detection_model()
    model.processor = load_detection_processor()
    return model


def setup_texify_model(device=None, dtype=None) -> GenerateVisionEncoderDecoderModel:
    if device:
        texify_model = load_texify_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=device, dtype=dtype)
    else:
        texify_model = load_texify_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=settings.TORCH_DEVICE_MODEL, dtype=settings.TEXIFY_DTYPE)
    texify_model.processor = load_texify_processor()
    return texify_model


def setup_layout_model(device=None, dtype=None) -> SuryaLayoutModel:
    if device:
        model = load_layout_model(device=device, dtype=dtype)
    else:
        model = load_layout_model()
    model.processor = load_layout_processor()
    return model


def create_model_dict(device=None, dtype=None) -> dict:
    return {
        "layout_model": setup_layout_model(device, dtype),
        "texify_model": setup_texify_model(device, dtype),
        "recognition_model": setup_recognition_model(device, dtype),
        "table_rec_model": setup_table_rec_model(device, dtype),
        "detection_model": setup_detection_model(device, dtype),
    }