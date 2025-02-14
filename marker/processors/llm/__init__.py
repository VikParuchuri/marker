import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, TypedDict, List, Sequence

from pydantic import BaseModel
from tqdm import tqdm
from PIL import Image

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups import PageGroup
from marker.services import BaseService
from marker.settings import settings
from marker.util import assign_config


class PromptData(TypedDict):
    prompt: str
    image: Image.Image
    block: Block
    schema: BaseModel
    page: PageGroup
    additional_data: dict | None


class BlockData(TypedDict):
    page: PageGroup
    block: Block


class BaseLLMProcessor(BaseProcessor):
    """
    A processor for using LLMs to convert blocks.
    """
    google_api_key: Annotated[
        str,
        "The Google API key to use for the Gemini model.",
    ] = settings.GOOGLE_API_KEY
    model_name: Annotated[
        str,
        "The name of the Gemini model to use.",
    ] = "gemini-2.0-flash"
    max_concurrency: Annotated[
        int,
        "The maximum number of concurrent requests to make to the Gemini model.",
    ] = 3
    image_expansion_ratio: Annotated[
        float,
        "The ratio to expand the image by when cropping.",
    ] = 0.01
    use_llm: Annotated[
        bool,
        "Whether to use the LLM model.",
    ] = False
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    block_types = None

    def __init__(self, llm_service: BaseService, config=None):
        super().__init__(config)

        self.llm_service = None
        if not self.use_llm:
            return

        self.llm_service = llm_service

    def extract_image(self, document: Document, image_block: Block, remove_blocks: Sequence[BlockTypes] | None = None) -> Image.Image:
        return image_block.get_image(
            document,
            highres=True,
            expansion=(self.image_expansion_ratio, self.image_expansion_ratio),
            remove_blocks=remove_blocks
        )


class BaseLLMComplexBlockProcessor(BaseLLMProcessor):
    """
    A processor for using LLMs to convert blocks with more complex logic.
    """
    def __call__(self, document: Document):
        if not self.use_llm or self.llm_service is None:
            return

        try:
            self.rewrite_blocks(document)
        except Exception as e:
            print(f"Error rewriting blocks in {self.__class__.__name__}: {e}")

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        raise NotImplementedError()

    def rewrite_blocks(self, document: Document):
        # Don't show progress if there are no blocks to process
        total_blocks = sum(len(page.contained_blocks(document, self.block_types)) for page in document.pages)
        if total_blocks == 0:
            return

        pbar = tqdm(desc=f"{self.__class__.__name__} running", disable=self.disable_tqdm)
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for future in as_completed([
                executor.submit(self.process_rewriting, document, page, block)
                for page in document.pages
                for block in page.contained_blocks(document, self.block_types)
            ]):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()


class BaseLLMSimpleBlockProcessor(BaseLLMProcessor):
    """
    A processor for using LLMs to convert single blocks.
    """

    # Override init since we don't need an llmservice here
    def __init__(self, config=None):
        assign_config(self, config)

    def __call__(self, result: dict, prompt_data: PromptData, document: Document):
        try:
            self.rewrite_block(result, prompt_data, document)
        except Exception as e:
            print(f"Error rewriting block in {self.__class__.__name__}: {e}")
            traceback.print_exc()

    def inference_blocks(self, document: Document) -> List[BlockData]:
        blocks = []
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                blocks.append({
                    "page": page,
                    "block": block
                })
        return blocks

    def block_prompts(self, document: Document) -> List[PromptData]:
        raise NotImplementedError()

    def rewrite_block(self, response: dict, prompt_data: PromptData, document: Document):
        raise NotImplementedError()


