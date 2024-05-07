from typing import List

from marker.schema.page import Page


def get_image_filename(page: Page, image_idx):
    return f"{page.pnum}_image_{image_idx}.png"


def images_to_dict(pages: List[Page]):
    images = {}
    for page in pages:
        if page.images is None:
            continue
        for image_idx, image in enumerate(page.images):
            image_filename = get_image_filename(page, image_idx)
            images[image_filename] = image
    return images
