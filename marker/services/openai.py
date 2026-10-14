import json
import os
import time
from typing import Annotated, List
from urllib.parse import urlparse

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
        "gpt-5-mini"
    )
    openai_api_key: Annotated[
        str, "The API key to use for the OpenAI-like service."
    ] = os.environ.get("OPENAI_API_KEY")
    openai_image_format: Annotated[
        str,
        "The image format to use for the OpenAI-like service. Use 'png' for better compatability",
    ] = "webp"

    def process_images(self, images: List[Image.Image]) -> List[dict]:
        """
        Generate the base-64 encoded message to send to an
        openAI-compatabile multimodal model.

        Args:
            images: Image or list of PIL images to include
            format: Format to use for the image; use "png" for better compatability.

        Returns:
            A list of OpenAI-compatbile multimodal messages containing the base64-encoded images.
        """
        if isinstance(images, Image.Image):
            images = [images]

        img_fmt = self.openai_image_format
        return [
            {
                "type": "image_url",
                "image_url": {
                    "url": "data:image/{};base64,{}".format(
                        img_fmt, self.img_to_base64(img, format=img_fmt)
                    ),
                },
            }
            for img in images
        ]

    def __call__(
        self,
        prompt: str,
        image: PIL.Image.Image | List[PIL.Image.Image] | None,
        block: Block | None,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        if max_retries is None:
            max_retries = self.max_retries

        if timeout is None:
            timeout = self.timeout

        client = self.get_client()
        image_data = self.format_image_for_llm(image)

        messages = [
            {
                "role": "user",
                "content": [
                    *image_data,
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        total_tries = max_retries + 1
        for tries in range(1, total_tries + 1):
            try:
                # Ollama Cloud does not enforce JSON Schema / structured outputs.
                # Include the schema in the request and validate locally instead.
                if urlparse(self.openai_base_url).hostname == "ollama.com":
                    schema_prompt = (prompt + "\n\nReturn only JSON matching this schema:\n"
                                     + json.dumps(response_schema.model_json_schema(), ensure_ascii=False))
                    cloud_messages = [{"role": "user", "content": [*image_data, {"type": "text", "text": schema_prompt}]}]
                    options = {"max_tokens": self.max_output_tokens} if self.max_output_tokens else {}
                    response = client.chat.completions.create(
                        model=self.openai_model, messages=cloud_messages,
                        timeout=timeout, temperature=0, **options,
                    )
                    if response.choices[0].finish_reason == "length":
                        raise ValueError("Cloud response was truncated before completing the JSON")
                else:
                    response = client.chat.completions.parse(
                        extra_headers={"X-Title": "Marker", "HTTP-Referer": "https://github.com/datalab-to/marker"},
                        model=self.openai_model, messages=messages, timeout=timeout,
                        response_format=response_schema,
                    )
                response_text = response.choices[0].message.content
                total_tokens = response.usage.total_tokens if response.usage else 0
                if block:
                    block.update_metadata(
                        llm_tokens_used=total_tokens, llm_request_count=1
                    )
                # Some providers wrap JSON in one code fence despite the prompt.
                response_text = (response_text or "").strip()
                if response_text.startswith("```json\n") and response_text.endswith("```"):
                    response_text = response_text[8:-3].strip()
                return response_schema.model_validate_json(response_text).model_dump()
            except (APITimeoutError, RateLimitError) as e:
                # Rate limit exceeded
                if tries == total_tries:
                    # Last attempt failed. Give up
                    logger.error(
                        f"Rate limit error: {e}. Max retries reached. Giving up. (Attempt {tries}/{total_tries})",
                    )
                    break
                else:
                    wait_time = tries * self.retry_wait_time
                    logger.warning(
                        f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{total_tries})",
                    )
                    time.sleep(wait_time)
            except Exception as e:
                logger.error(f"OpenAI inference failed: {e}")
                break

        return {}

    def get_client(self) -> openai.OpenAI:
        return openai.OpenAI(api_key=self.openai_api_key, base_url=self.openai_base_url)
