import re
from typing import Optional

from pydantic import BaseModel

from marker.v2.schema import BlockTypes
from marker.v2.util import assign_config


class BaseRenderer:
    block_type: BlockTypes | None = None

    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, document):
        # Children are in reading order
        raise NotImplementedError

    @staticmethod
    def extract_image(document, image_id):
        image_block = document.get_block(image_id)
        page = document.get_page(image_block.page_id)
        page_img = page.highres_image
        image_box = image_block.polygon.rescale(page.polygon.size, page_img.size)
        cropped = page_img.crop(image_box.bbox)
        return cropped

    @staticmethod
    def merge_consecutive_tags(html, tag):
        if not html:
            return html

        def replace_whitespace(match):
            return match.group(1)

        pattern = fr'</{tag}>(\s*)<{tag}>'

        while True:
            new_merged = re.sub(pattern, replace_whitespace, html)
            if new_merged == html:
                break
            html = new_merged

        return html
