import base64
import io
import re
from collections import Counter
from typing import Optional

from bs4 import BeautifulSoup
from pydantic import BaseModel

from marker.schema import BlockTypes
from marker.schema.blocks.base import BlockId, BlockOutput
from marker.schema.document import Document
from marker.settings import settings
from marker.util import assign_config


class BaseRenderer:
    remove_blocks: list = [BlockTypes.PageHeader, BlockTypes.PageFooter]
    image_blocks: list = [BlockTypes.Picture, BlockTypes.Figure]
    extract_images: bool = True

    def __init__(self, config: Optional[BaseModel | dict] = None):
        assign_config(self, config)

    def __call__(self, document):
        # Children are in reading order
        raise NotImplementedError

    @staticmethod
    def extract_image(document: Document, image_id, to_base64=False):
        image_block = document.get_block(image_id)
        page = document.get_page(image_block.page_id)
        page_img = page.highres_image
        image_box = image_block.polygon.rescale(page.polygon.size, page_img.size)
        cropped = page_img.crop(image_box.bbox)
        if to_base64:
            image_buffer = io.BytesIO()
            cropped.save(image_buffer, format=settings.OUTPUT_IMAGE_FORMAT)
            cropped = base64.b64encode(image_buffer.getvalue()).decode(settings.OUTPUT_ENCODING)
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

    def generate_page_stats(self, document: Document, document_output):
        page_stats = []
        for page in document.pages:
            block_counts = Counter([str(block.block_type) for block in page.children]).most_common()
            page_stats.append({
                "page_id": page.page_id,
                "text_extraction_method": page.text_extraction_method,
                "block_counts": block_counts,
            })
        return page_stats

    def generate_document_metadata(self, document: Document, document_output):
        metadata =  {
            "table_of_contents": document.table_of_contents,
            "page_stats": self.generate_page_stats(document, document_output),
        }
        if document.debug_data_path is not None:
            metadata["debug_data_path"] = document.debug_data_path

        return metadata

    def extract_block_html(self, document: Document, block_output: BlockOutput):
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

            if ref_block_id.block_type in self.image_blocks and self.extract_images:
                images[ref_block_id] = self.extract_image(document, ref_block_id, to_base64=True)
            else:
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(content, 'html.parser'))

        if block_output.id.block_type in self.image_blocks and self.extract_images:
            images[block_output.id] = self.extract_image(document, block_output.id, to_base64=True)

        return str(soup), images
