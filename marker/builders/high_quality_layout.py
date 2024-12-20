import json
import time
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
from marker.providers.pdf import PdfProvider
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup
from marker.schema.registry import get_block_class
from marker.settings import settings


class HighQualityLayoutBuilder(LayoutBuilder):
    """
    A builder for relabelling blocks to improve the quality of the layout.

    Attributes:
        google_api_key (str):
            The Google API key to use for the Gemini model.
            Default is None.
        confidence_threshold (float):
            The confidence threshold to use for relabeling.
            Default is 0.8.
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
        gemini_relabelling_prompt (str):
            The prompt to use for relabelling blocks.
            Default is a string containing the Gemini relabelling prompt.
    """

    google_api_key: Optional[str] = settings.GOOGLE_API_KEY
    confidence_threshold: float = 0.7
    model_name: str = "gemini-1.5-flash"
    max_retries: int = 3
    max_concurrency: int = 3
    timeout: int = 60

    gemini_relabelling_prompt = """You are a layout expert specializing in document analysis.
Your task is to relabel layout blocks in images to improve the accuracy of an existing layout model.
You will be provided with an image of a layout block and the top k predictions from the current model, along with their confidence scores.
Your job is to analyze the image and choose the single most appropriate label from the provided top k predictions.
Do not invent any new labels. 
Carefully examine the image and consider the provided predictions. 
Choose the label you believe is the most accurate representation of the layout block.

Here are the top k predictions from the model followed by the image:

"""

    def __init__(self, layout_model: SuryaLayoutModel, ocr_error_model: DistilBertForSequenceClassification, config=None):
        self.layout_model = layout_model
        self.ocr_error_model = ocr_error_model

        self.model = None
        if self.google_api_key is None:
            raise ValueError("Google API key is not set")

        genai.configure(api_key=self.google_api_key)
        self.model = genai.GenerativeModel(self.model_name)

    def __call__(self, document: Document, provider: PdfProvider):
        super().__call__(document, provider)

        self.relabel_blocks(document)

    def relabel_blocks(self, document: Document):
        pbar = tqdm(desc="High quality layout relabelling")
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = []
            for page in document.pages:
                for block_id in page.structure:
                    block = page.get_block(block_id)
                    if block.top_k:
                        confidence = block.top_k.get(block.block_type)
                        if confidence < self.confidence_threshold:
                            futures.append(executor.submit(self.process_block_relabelling, page, block))

            for future in as_completed(futures):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_block_relabelling(self, page: PageGroup, block: Block):
        topk = {str(k): round(v, 3) for k, v in block.top_k.items()}

        prompt = self.gemini_relabelling_prompt + '```json' + json.dumps(topk) + '```\n'
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

        response = self.generate(prompt, image, response_schema)
        generated_label = None
        if response and "label" in response:
            generated_label = response["label"]

        if generated_label and generated_label != str(block.block_type):
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

    def generate(self, prompt: str, image: PIL.Image.Image, response_schema: content.Schema):
        tries = 0
        while tries < self.max_retries:
            try:
                responses = self.model.generate_content(
                    [prompt, image],
                    stream=False,
                    generation_config={
                        "temperature": 0,
                        "response_schema": response_schema,
                        "response_mime_type": "application/json",
                    },
                    request_options={'timeout': self.timeout}
                )
                output = responses.candidates[0].content.parts[0].text
                return json.loads(output)

            except ResourceExhausted as e:
                tries += 1
                wait_time = tries * 2
                print(f"ResourceExhausted: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{self.max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(e)
                break

        return {}
