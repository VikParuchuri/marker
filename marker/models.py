import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS


from surya.model.detection.model import load_model as load_detection_model, load_processor as load_detection_processor
from texify.model.model import load_model as load_texify_model
from texify.model.processor import load_processor as load_texify_processor
from marker.settings import settings
from surya.model.recognition.model import load_model as load_recognition_model
from surya.model.recognition.processor import load_processor as load_recognition_processor
from surya.model.ordering.model import load_model as load_order_model
from surya.model.ordering.processor import load_processor as load_order_processor
from surya.model.table_rec.model import load_model as load_table_model
from surya.model.table_rec.processor import load_processor as load_table_processor


def setup_table_rec_model(device=None, dtype=None):
    if device:
        table_model = load_table_model(device=device, dtype=dtype)
    else:
        table_model = load_table_model()
    table_model.processor = load_table_processor()
    return table_model


def setup_recognition_model(device=None, dtype=None):
    if device:
        rec_model = load_recognition_model(device=device, dtype=dtype)
    else:
        rec_model = load_recognition_model()
    rec_model.processor = load_recognition_processor()
    return rec_model


def setup_detection_model(device=None, dtype=None):
    if device:
        model = load_detection_model(device=device, dtype=dtype)
    else:
        model = load_detection_model()
    model.processor = load_detection_processor()
    return model


def setup_texify_model(device=None, dtype=None):
    if device:
        texify_model = load_texify_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=device, dtype=dtype)
    else:
        texify_model = load_texify_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=settings.TORCH_DEVICE_MODEL, dtype=settings.TEXIFY_DTYPE)
    texify_model.processor = load_texify_processor()
    return texify_model


def setup_layout_model(device=None, dtype=None):
    if device:
        model = load_detection_model(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT, device=device, dtype=dtype)
    else:
        model = load_detection_model(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
    model.processor = load_detection_processor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
    return model


def setup_order_model(device=None, dtype=None):
    if device:
        model = load_order_model(device=device, dtype=dtype)
    else:
        model = load_order_model()
    model.processor = load_order_processor()
    return model


def load_all_models(device=None, dtype=None):
    if device is not None:
        assert dtype is not None, "Must provide dtype if device is provided"

    # langs is optional list of languages to prune from recognition MoE model
    detection = setup_detection_model(device, dtype)
    layout = setup_layout_model(device, dtype)
    order = setup_order_model(device, dtype)

    # Only load recognition model if we'll need it for all pdfs
    ocr = setup_recognition_model(device, dtype)
    texify = setup_texify_model(device, dtype)
    table_model = setup_table_rec_model(device, dtype)
    model_lst = [texify, layout, order, detection, ocr, table_model]
    return model_lst