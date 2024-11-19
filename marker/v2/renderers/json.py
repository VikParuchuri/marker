from __future__ import annotations

import base64
import io
from typing import List, Dict

from bs4 import BeautifulSoup
from pydantic import BaseModel

from marker.v2.schema.blocks import Block
from marker.v2.renderers import BaseRenderer
from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import BlockId
from marker.v2.schema.registry import get_block_class


class JSONBlockOutput(BaseModel):
    id: str
    block_type: str
    html: str
    polygon: List[List[float]]
    children: List[JSONBlockOutput] | None = None
    section_hierarchy: Dict[int, str] | None = None
    images: dict | None = None


class JSONOutput(BaseModel):
    children: List[JSONBlockOutput]
    block_type: BlockTypes = BlockTypes.Document


def reformat_section_hierarchy(section_hierarchy):
    new_section_hierarchy = {}
    for key, value in section_hierarchy.items():
        new_section_hierarchy[key] = str(value)
    return new_section_hierarchy


class JSONRenderer(BaseRenderer):
    image_blocks: list = [BlockTypes.Picture, BlockTypes.Figure]
    page_blocks: list = [BlockTypes.Page]

    def extract_json(self, document, block_output):
        cls = get_block_class(block_output.id.block_type)
        if cls.__base__ == Block:
            html, images = self.extract_html(document, block_output)
            return JSONBlockOutput(
                html=html,
                polygon=block_output.polygon.polygon,
                id=str(block_output.id),
                block_type=str(block_output.id.block_type),
                images=images,
                section_hierarchy=reformat_section_hierarchy(block_output.section_hierarchy)
            )
        else:
            children = []
            for child in block_output.children:
                child_output = self.extract_json(document, child)
                children.append(child_output)

            return JSONBlockOutput(
                html=block_output.html,
                polygon=block_output.polygon.polygon,
                id=str(block_output.id),
                block_type=str(block_output.id.block_type),
                children=children,
                section_hierarchy=reformat_section_hierarchy(block_output.section_hierarchy)
            )

    def extract_html(self, document, block_output):
        soup = BeautifulSoup(block_output.html, 'html.parser')

        content_refs = soup.find_all('content-ref')
        ref_block_id = None
        images = {}
        for ref in content_refs:
            src = ref.get('src')
            sub_images = {}
            for item in block_output.children:
                if item.id == src:
                    content, sub_images = self.extract_html(document, item)
                    ref_block_id: BlockId = item.id
                    break

            if ref_block_id.block_type in self.image_blocks:
                image = self.extract_image(document, ref_block_id)
                image_buffer = io.BytesIO()
                image.save(image_buffer, format='PNG')
                images[ref_block_id] = base64.b64encode(image_buffer.getvalue()).decode('utf-8')
            else:
                images.update(sub_images)
                ref.replace_with(BeautifulSoup(content, 'html.parser'))

        return str(soup), images

    def __call__(self, document) -> JSONOutput:
        document_output = document.render()
        json_output = []
        for page_output in document_output.children:
            json_output.append(self.extract_json(document, page_output))
        return JSONOutput(
            children=json_output,
        )
