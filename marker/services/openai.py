import base64
import json
import time
from io import BytesIO
from typing import Annotated, List, Union

import openai
import PIL
from marker.logger import get_logger
from openai import APITimeoutError, RateLimitError
from PIL import Image
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.services import BaseService

logger = get_logger()


class OpenAIService(BaseService):
    openai_base_url: Annotated[
        str, "The base url to use for OpenAI-like models.  No trailing slash."
    ] = "https://api.openai.com/v1"
    openai_model: Annotated[str, "The model name to use for OpenAI-like model."] = (
        "gpt-4o-mini"
    )
    openai_api_key: Annotated[
        str, "The API key to use for the OpenAI-like service."
    ] = None
    openai_image_format: Annotated[
        str, "The image format to use for the OpenAI-like service. Use 'png' for better compatability"
    ] = 'webp'

    def image_to_base64(self, image: PIL.Image.Image) -> str:
        """
        Convert PIL image to base64 string

        Args:
            image: Input PIL Image
            format: Format to use for the image; use "png" for better compatability.

        Returns:
            Base-64 encoded image (in PNG format) to pass to LLM.
        """
        image_bytes = BytesIO()
        image.save(image_bytes, format=self.openai_image_format)
        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    def prepare_images(
        self, images: Union[Image.Image, List[Image.Image]]
    ) -> List[dict]:
        """
        Generate the base-64 encoded message to send to an
        openAI-compatabile multimodal model.

        Args:
            images: Image or list of PIL images to include
            format: Format to use for the image; use "png" for better compatability.

        Returns:

        """
        if isinstance(images, Image.Image):
            images = [images]

        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/{};base64,{}".format(
                        self.openai_image_format,
                        self.image_to_base64(img)
                    ),
                },
            }
            for img in images
        ]

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        if not isinstance(image, list):
            image = [image]

        client = self.get_client()
        image_data = self.prepare_images(image)

        messages = [
            {
                "role": "user",
                "content": [
                    *image_data,
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        tries = 0
        while tries < max_retries:
            try:
                response = client.beta.chat.completions.parse(
                    extra_headers={
                        "X-Title": "Marker",
                        "HTTP-Referer": "https://github.com/VikParuchuri/marker",
                    },
                    model=self.openai_model,
                    messages=messages,
                    timeout=timeout,
                    response_format=response_schema,
                )
                response_text = response.choices[0].message.content
                total_tokens = response.usage.total_tokens
                block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)
                return json.loads(response_text)
            except (APITimeoutError, RateLimitError) as e:
                # Rate limit exceeded
                tries += 1
                wait_time = tries * self.retry_wait_time
                logger.warning(
                    f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})"
                )
                time.sleep(wait_time)
            except Exception as e:
                logger.error(f"OpenAI inference failed: {e}")
                break

        return {}

    def get_client(self) -> openai.OpenAI:
        return openai.OpenAI(api_key=self.openai_api_key, base_url=self.openai_base_url)
