from marker.cleaners.equations import load_texify_model
from marker.ordering import load_ordering_model
from marker.postprocessors.editor import load_editing_model
from marker.segmentation import load_layout_model


def load_all_models():
    edit = load_editing_model()
    order = load_ordering_model()
    layout = load_layout_model()
    texify = load_texify_model()
    model_lst = [texify, layout, order, edit]
    return model_lst
