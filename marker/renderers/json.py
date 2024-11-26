from __future__ import annotations

from typing import List, Dict

from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.renderers import BaseRenderer
from marker.schema import BlockTypes
from marker.schema.registry import get_block_class


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
    metadata: dict


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
            html, images = self.extract_block_html(document, block_output)
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

    def __call__(self, document) -> JSONOutput:
        document_output = document.render()
        json_output = []
        for page_output in document_output.children:
            json_output.append(self.extract_json(document, page_output))
        return JSONOutput(
            children=json_output,
            metadata=self.generate_document_metadata(document, document_output)
        )
