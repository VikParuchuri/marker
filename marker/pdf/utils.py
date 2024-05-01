def rescale_bbox(orig_dim, new_dim, bbox):
    page_width, page_height = new_dim[2] - new_dim[0], new_dim[3] - new_dim[1]
    detected_width, detected_height = orig_dim[2] - orig_dim[0], orig_dim[3] - orig_dim[1]
    width_scaler = detected_width / page_width
    height_scaler = detected_height / page_height

    bbox = [bbox[0] / width_scaler, bbox[1] / height_scaler, bbox[2] / width_scaler, bbox[3] / height_scaler]
    return bbox