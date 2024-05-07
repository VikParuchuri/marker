from marker.postprocessors.editor import load_editing_model
from surya.model.detection import segformer
from texify.model.model import load_model as load_texify_model
from texify.model.processor import load_processor as load_texify_processor
from marker.settings import settings
from surya.model.recognition.model import load_model as load_recognition_model
from surya.model.recognition.processor import load_processor as load_recognition_processor
from surya.model.ordering.model import load_model as load_order_model
from surya.model.ordering.processor import load_processor as load_order_processor


def setup_recognition_model(langs):
    rec_model = load_recognition_model(langs=langs)
    rec_processor = load_recognition_processor()
    rec_model.processor = rec_processor
    return rec_model


def setup_detection_model():
    model = segformer.load_model()
    processor = segformer.load_processor()
    model.processor = processor
    return model


def setup_texify_model():
    texify_model = load_texify_model(checkpoint=settings.TEXIFY_MODEL_NAME, device=settings.TORCH_DEVICE_MODEL, dtype=settings.TEXIFY_DTYPE)
    texify_processor = load_texify_processor()
    texify_model.processor = texify_processor
    return texify_model


def setup_layout_model():
    model = segformer.load_model(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
    processor = segformer.load_processor(checkpoint=settings.LAYOUT_MODEL_CHECKPOINT)
    model.processor = processor
    return model


def setup_order_model():
    model = load_order_model()
    processor = load_order_processor()
    model.processor = processor
    return model


def load_all_models(langs=None):
    # langs is optional list of languages to prune from recognition MoE model
    detection = setup_detection_model()
    layout = setup_layout_model()
    order = setup_order_model()
    edit = load_editing_model()
    ocr = setup_recognition_model(langs) if settings.OCR_ENGINE == "surya" else None
    texify = setup_texify_model()
    model_lst = [texify, layout, order, edit, detection, ocr]
    return model_lst
