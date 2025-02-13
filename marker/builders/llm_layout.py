from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated

from surya.layout import LayoutPredictor
from tqdm import tqdm
from pydantic import BaseModel

from marker.builders.layout import LayoutBuilder
from marker.services import BaseService
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
    """

    google_api_key: Annotated[
        str,
        "The Google API key to use for the Gemini model.",
    ] = settings.GOOGLE_API_KEY
    confidence_threshold: Annotated[
        float,
        "The confidence threshold to use for relabeling (anything below is relabeled).",
    ] = 0.7
    picture_height_threshold: Annotated[
        float,
        "The height threshold for pictures that may actually be complex regions. (anything above this ratio against the page is relabeled)",
    ] = 0.8
    model_name: Annotated[
        str,
        "The name of the Gemini model to use.",
    ] = "gemini-2.0-flash"
    max_concurrency: Annotated[
        int,
        "The maximum number of concurrent requests to make to the Gemini model.",
    ] = 3
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    topk_relabelling_prompt: Annotated[
        str,
        "The prompt to use for relabelling blocks.",
        "Default is a string containing the Gemini relabelling prompt."
    ] = """You're a layout expert specializing in document analysis.
Your task is to relabel layout blocks in images to improve the accuracy of an existing layout model.
You will be provided with an image of a layout block and the top k predictions from the current model, along with the per-label confidence scores.
Your job is to analyze the image and choose the single most appropriate label from the provided top k predictions.
Do not invent any new labels. 
Carefully examine the image and consider the provided predictions.  Take the model confidence scores into account.  The confidence is reported on a 0-1 scale, with 1 being 100% confident.  If the existing label is the most appropriate, you should not change it.
**Instructions**
1. Analyze the image and consider the provided top k predictions.
2. Write a short description of the image, and which of the potential labels you believe is the most accurate representation of the layout block.
3. Choose the single most appropriate label from the provided top k predictions.

Here are descriptions of the layout blocks you can choose from:

{potential_labels}

Here are the top k predictions from the model:

{top_k}
"""
    complex_relabeling_prompt: Annotated[
        str,
        "The prompt to use for complex relabelling blocks.",
        "Default is a string containing the complex relabelling prompt."
    ] = """You're a layout expert specializing in document analysis.
Your task is to relabel layout blocks in images to improve the accuracy of an existing layout model.
You will be provided with an image of a layout block and some potential labels that might be appropriate.
Your job is to analyze the image and choose the single most appropriate label from the provided labels.
Do not invent any new labels. 
**Instructions**
1. Analyze the image and consider the potential labels.
2. Write a short description of the image, and which of the potential labels you believe is the most accurate representation of the layout block.
3. Choose the single most appropriate label from the provided labels.

Potential labels:

{potential_labels}

Respond only with one of `Figure`, `Picture`, `ComplexRegion`, `Table`, or `Form`.
"""

    def __init__(self, layout_model: LayoutPredictor, llm_service: BaseService, config=None):
        super().__init__(layout_model, config)

        self.llm_service = llm_service

    def __call__(self, document: Document, provider: PdfProvider):
        super().__call__(document, provider)
        try:
            self.relabel_blocks(document)
        except Exception as e:
            print(f"Error relabelling blocks: {e}")

    def relabel_blocks(self, document: Document):
        pbar = tqdm(desc="LLM layout relabelling", disable=self.disable_tqdm)
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            futures = []
            for page in document.pages:
                for block_id in page.structure:
                    block = page.get_block(block_id)
                    if block.top_k:
                        confidence = block.top_k.get(block.block_type)
                        # Case when the block is detected as a different type with low confidence
                        if confidence < self.confidence_threshold:
                            futures.append(executor.submit(self.process_block_topk_relabeling, document, page, block))
                        # Case when the block is detected as a picture or figure, but is actually complex
                        elif block.block_type in (BlockTypes.Picture, BlockTypes.Figure, BlockTypes.SectionHeader) and block.polygon.height > page.polygon.height * self.picture_height_threshold:
                            futures.append(executor.submit(self.process_block_complex_relabeling, document, page, block))

            for future in as_completed(futures):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def process_block_topk_relabeling(self, document: Document, page: PageGroup, block: Block):
        topk_types = list(block.top_k.keys())
        potential_labels = ""
        for block_type in topk_types:
            label_cls = get_block_class(block_type)
            potential_labels += f"- `{block_type}` - {label_cls.model_fields['block_description'].default}\n"

        topk = ""
        for k,v in block.top_k.items():
            topk += f"- `{k}` - Confidence {round(v, 3)}\n"

        prompt = self.topk_relabelling_prompt.replace("{potential_labels}", potential_labels).replace("{top_k}", topk)

        return self.process_block_relabeling(document, page, block, prompt)

    def process_block_complex_relabeling(self, document: Document, page: PageGroup, block: Block):
        potential_labels = ""
        for block_type in [BlockTypes.Figure, BlockTypes.Picture, BlockTypes.ComplexRegion, BlockTypes.Table, BlockTypes.Form]:
            label_cls = get_block_class(block_type)
            potential_labels += f"- `{block_type}` - {label_cls.model_fields['block_description'].default}\n"

        complex_prompt = self.complex_relabeling_prompt.replace("{potential_labels}", potential_labels)
        return self.process_block_relabeling(document, page, block, complex_prompt)

    def process_block_relabeling(self, document: Document, page: PageGroup, block: Block, prompt: str):
        image = self.extract_image(document, block)

        response = self.llm_service(
            prompt,
            image,
            block,
            LayoutSchema
        )
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

    def extract_image(self, document: Document, image_block: Block, expand: float = 0.01):
        return image_block.get_image(document, highres=False, expansion=(expand, expand))


class LayoutSchema(BaseModel):
    image_description: str
    label: str
