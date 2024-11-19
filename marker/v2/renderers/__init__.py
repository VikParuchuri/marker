import base64
import io
import re
from typing import Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks.base import BlockOutput, BlockId
from marker.v2.util import assign_config


class BaseRenderer:
    remove_blocks: list = [BlockTypes.PageHeader, BlockTypes.PageFooter]
    image_blocks: list = [BlockTypes.Picture, BlockTypes.Figure]

    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, document):
        # Children are in reading order
        raise NotImplementedError

    @staticmethod
    def extract_image(document, image_id, to_base64=False):
        image_block = document.get_block(image_id)
        page = document.get_page(image_block.page_id)
        page_img = page.highres_image
        image_box = image_block.polygon.rescale(page.polygon.size, page_img.size)
        cropped = page_img.crop(image_box.bbox)
        if to_base64:
            image_buffer = io.BytesIO()
            cropped.save(image_buffer, format='PNG')
            cropped = base64.b64encode(image_buffer.getvalue()).decode('utf-8')
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

    def compute_toc(self, document, block_output: BlockOutput):
        toc = []
        if hasattr(block_output, "id") and block_output.id.block_type == BlockTypes.SectionHeader:
            toc.append({
                "title": self.extract_block_html(document, block_output)[0],
                "level": document.get_block(block_output.id).heading_level,
                "page": block_output.id.page_id
            })

        for child in block_output.children:
            child_toc = self.compute_toc(document, child)
            if child_toc:
                toc.extend(child_toc)
        return toc

    def generate_document_metadata(self, document, document_output):
        toc = self.compute_toc(document, document_output)
        return {
            "table_of_contents": toc
        }

    def extract_block_html(self, document, block_output):
        soup = BeautifulSoup(block_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get('src')
            sub_images = {}
            for item in block_output.children:
                if item.id == src:
                    content, sub_images_ = self.extract_block_html(document, item)
                    sub_images.update(sub_images_)
                    ref_block_id: BlockId = item.id
                    break

            if ref_block_id.block_type in self.image_blocks:
                images[ref_block_id] = self.extract_image(document, ref_block_id, to_base64=True)
            else:
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(content, 'html.parser'))

        if block_output.id.block_type in self.image_blocks:
            images[block_output.id] = self.extract_image(document, block_output.id, to_base64=True)

        return str(soup), images

