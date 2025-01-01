import json
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import google.generativeai as genai
import PIL
from google.ai.generativelanguage_v1beta.types import content
from google.api_core.exceptions import ResourceExhausted
from surya.model.layout.encoderdecoder import SuryaLayoutModel
from surya.model.ocr_error.model import DistilBertForSequenceClassification
from tqdm import tqdm

from marker.builders.layout import LayoutBuilder
from marker.processors.llm import GoogleModel
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class
from marker.settings import settings


class LLMLayoutBuilder(LayoutBuilder):
    """
    A builder for relabelling blocks to improve the quality of the layout.

    Attributes:
        google_api_key (str):
            The Google API key to use for the Gemini model.
            Default is None.
        confidence_threshold (float):
            The confidence threshold to use for relabeling.
            Default is 0.75.
        picture_height_threshold (float):
            The height threshold for pictures that may actually be complex regions.
        model_name (str):
            The name of the Gemini model to use.
            Default is "gemini-1.5-flash".
        max_retries (int):
            The maximum number of retries to use for the Gemini model.
            Default is 3.
        max_concurrency (int):
            The maximum number of concurrent requests to make to the Gemini model.
            Default is 3.
        timeout (int):
            The timeout for requests to the Gemini model.
            Default is 60 seconds.
        topk_relabelling_prompt (str):
            The prompt to use for relabelling blocks.
            Default is a string containing the Gemini relabelling prompt.
        complex_relabeling_prompt (str):
            The prompt to use for complex relabelling blocks.
            Default is a string containing the complex relabelling prompt.
    """

    google_api_key: Optional[str] = settings.GOOGLE_API_KEY
    confidence_threshold: float = 0.75
    picture_height_threshold: float = 0.8
    model_name: str = "gemini-1.5-flash"
    max_retries: int = 3
    max_concurrency: int = 3
    timeout: int = 60

    topk_relabelling_prompt = """You are a layout expert specializing in document analysis.
Your task is to relabel layout blocks in images to improve the accuracy of an existing layout model.
You will be provided with an image of a layout block and the top k predictions from the current model, along with their confidence scores.
Your job is to analyze the image and choose the single most appropriate label from the provided top k predictions.
Do not invent any new labels. 
Carefully examine the image and consider the provided predictions. 
Choose the label you believe is the most accurate representation of the layout block.

Here are the top k predictions from the model followed by the image:

"""
    complex_relabeling_prompt = """You are a layout expert specializing in document analysis.
Your task is to relabel layout blocks in images to improve the accuracy of an existing layout model.
You will be provided with an image of a layout block and some potential labels.
Your job is to analyze the image and choose the single most appropriate label from the provided labels.
Do not invent any new labels. 
Carefully examine the image and consider the provided predictions. 
Choose the label you believe is the most accurate representation of the layout block.

Potential labels:

- Picture
- Table
- Form
- Figure - A graph or diagram with text.
- ComplexRegion - a complex region containing multiple text and other elements.

Respond only with one of `Figure`, `Picture`, `ComplexRegion`, `Table`, or `Form`.

Here is the image of the layout block:
"""

    def __init__(self, layout_model: SuryaLayoutModel, ocr_error_model: DistilBertForSequenceClassification, config=None):
        super().__init__(layout_model, ocr_error_model, config)

        self.model = GoogleModel(self.google_api_key, self.model_name)

    def __call__(self, document: Document, provider: PdfProvider):
        super().__call__(document, provider)
        try:
            self.relabel_blocks(document)
        except Exception as e:
            print(f"Error relabelling blocks: {e}")

    def relabel_blocks(self, document: Document):
        pbar = tqdm(desc="LLM layout relabelling")
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = []
            for page in document.pages:
                for block_id in page.structure:
                    block = page.get_block(block_id)
                    if block.top_k:
                        confidence = block.top_k.get(block.block_type)
                        # Case when the block is detected as a different type with low confidence
                        if confidence < self.confidence_threshold:
                            futures.append(executor.submit(self.process_block_topk_relabeling, page, block))
                        # Case when the block is detected as a picture or figure, but is actually complex
                        elif block.block_type in (BlockTypes.Picture, BlockTypes.Figure, BlockTypes.SectionHeader) and block.polygon.height > page.polygon.height * self.picture_height_threshold:
                            futures.append(executor.submit(self.process_block_complex_relabeling, page, block))

            for future in as_completed(futures):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_block_topk_relabeling(self, page: PageGroup, block: Block):
        topk = {str(k): round(v, 3) for k, v in block.top_k.items()}

        prompt = self.topk_relabelling_prompt + '```json' + json.dumps(topk) + '```\n'
        return self.process_block_relabeling(page, block, prompt)

    def process_block_complex_relabeling(self, page: PageGroup, block: Block):
        complex_prompt = self.complex_relabeling_prompt
        return self.process_block_relabeling(page, block, complex_prompt)


    def process_block_relabeling(self, page: PageGroup, block: Block, prompt: str):
        image = self.extract_image(page, block)
        response_schema = content.Schema(
            type=content.Type.OBJECT,
            enum=[],
            required=["label"],
            properties={
                "label": content.Schema(
                    type=content.Type.STRING,
                ),
            },
        )

        response = self.model.generate_response(prompt, image, block, response_schema)
        generated_label = None
        if response and "label" in response:
            generated_label = response["label"]

        if generated_label and generated_label != str(block.block_type) and generated_label in [str(t) for t in BlockTypes]:
            generated_block_class = get_block_class(BlockTypes[generated_label])
            generated_block = generated_block_class(
                polygon=block.polygon,
                page_id=block.page_id,
                structure=block.structure,
            )
            page.replace_block(block, generated_block)

    def extract_image(self, page: PageGroup, image_block: Block, expand: float = 0.01):
        page_img = page.lowres_image
        image_box = image_block.polygon\
            .rescale(page.polygon.size, page_img.size)\
            .expand(expand, expand)
        cropped = page_img.crop(image_box.bbox)
        return cropped