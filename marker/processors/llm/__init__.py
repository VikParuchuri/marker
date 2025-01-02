from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from tqdm import tqdm

from marker.processors import BaseProcessor
from marker.processors.llm.utils import GoogleModel
from marker.schema.blocks import Block
from marker.schema.document import Document
from marker.schema.groups import PageGroup
from marker.settings import settings


class BaseLLMProcessor(BaseProcessor):
    """
    A processor for using LLMs to convert blocks.
    Attributes:
        google_api_key (str):
            The Google API key to use for the Gemini model.
            Default is None.
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
        gemini_rewriting_prompt (str):
            The prompt to use for rewriting text.
            Default is a string containing the Gemini rewriting prompt.
        use_llm (bool):
            Whether to use the LLM model.
            Default is False.
    """

    google_api_key: Optional[str] = settings.GOOGLE_API_KEY
    model_name: str = "gemini-1.5-flash"
    use_llm: bool = False
    max_retries: int = 3
    max_concurrency: int = 3
    timeout: int = 60
    image_expansion_ratio: float = 0.01
    gemini_rewriting_prompt = None
    block_types = None

    def __init__(self, config=None):
        super().__init__(config)

        self.model = None
        if not self.use_llm:
            return

        self.model = GoogleModel(self.google_api_key, self.model_name)

    def __call__(self, document: Document):
        if not self.use_llm or self.model is None:
            return

        try:
            self.rewrite_blocks(document)
        except Exception as e:
            print(f"Error rewriting blocks in {self.__class__.__name__}: {e}")

    def process_rewriting(self, document: Document, page: PageGroup, block: Block):
        raise NotImplementedError()

    def rewrite_blocks(self, document: Document):
        pbar = tqdm(desc=f"{self.__class__.__name__} running")
        with ThreadPoolExecutor(max_workers=self.max_concurrency) as executor:
            for future in as_completed([
                executor.submit(self.process_rewriting, document, page, block)
                for page in document.pages
                for block in page.contained_blocks(document, self.block_types)
            ]):
                future.result()  # Raise exceptions if any occurred
                pbar.update(1)

        pbar.close()

    def extract_image(self, page: PageGroup, image_block: Block):
        page_img = page.lowres_image
        image_box = image_block.polygon\
            .rescale(page.polygon.size, page_img.size)\
            .expand(self.image_expansion_ratio, self.image_expansion_ratio)
        cropped = page_img.crop(image_box.bbox)
        return cropped