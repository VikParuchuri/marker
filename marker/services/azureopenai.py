import time
import json
import base64
from io import BytesIO
from typing import Annotated, List, Union

import openai
from openai import RateLimitError, OpenAIError
from PIL import Image
from pydantic import BaseModel

from marker.services import BaseService
from marker.schema.blocks import Block


class AzureOpenAIService(BaseService):
    """
    A service that calls Azure OpenAI for ChatCompletion with images + text prompts.
    """

    # Azure OpenAI configuration
    azure_base_url: Annotated[
        str, "The base URL for your Azure OpenAI resource (no trailing slash)."
    ] = "https://YOUR-RESOURCE-NAME.openai.azure.com"
    azure_api_key: Annotated[str, "Your Azure OpenAI key"] = None
    azure_api_version: Annotated[str, "Azure OpenAI API version."] = (
        "2023-03-15-preview"
    )
    azure_deployment_name: Annotated[
        str, "The deployment name for your model in Azure."
    ] = "gpt-4o"  # Example deployment name

    # Standard fallback if not provided
    max_retries: int = 3
    timeout: int = 60

    def image_to_base64(self, image: Image.Image) -> str:
        image_bytes = BytesIO()
        image.save(image_bytes, format="WEBP")
        return base64.b64encode(image_bytes.getvalue()).decode("utf-8")

    def prepare_images(
        self, images: Union[Image.Image, List[Image.Image]]
    ) -> List[dict]:
        if isinstance(images, Image.Image):
            images = [images]
        return [
            {
                "type": "image_url",
                "image_url": f"data:image/webp;base64,{self.image_to_base64(img)}",
            }
            for img in images
        ]

    def get_client(self) -> openai:
        """
        Configures and returns the openai module as an Azure OpenAI client.
        """
        openai.api_type = "azure"
        openai.api_base = self.azure_base_url
        openai.api_version = self.azure_api_version
        openai.api_key = self.azure_api_key
        return openai

    def __call__(
        self,
        prompt: str,
        image: Union[Image.Image, List[Image.Image]],
        block: Block,
        response_schema: type[BaseModel],
        max_retries: int | None = None,
        timeout: int | None = None,
    ):
        """
        Make a ChatCompletion request to Azure OpenAI with a text+image prompt.
        Parses the model's output as JSON and validates it against the provided schema.
        """
        if max_retries is None:
            max_retries = self.max_retries
        if timeout is None:
            timeout = self.timeout

        if not isinstance(image, list):
            image = [image]

        image_data = self.prepare_images(image)
        messages = [
            {
                "role": "user",
                "content": json.dumps(
                    [
                        *image_data,
                        {"type": "text", "text": prompt},
                    ]
                ),
            }
        ]

        client = self.get_client()

        tries = 0
        while tries < max_retries:
            try:
                response = client.ChatCompletion.create(
                    engine=self.azure_deployment_name,
                    messages=messages,
                    timeout=timeout,
                )

                response_text = response.choices[0].message["content"]
                usage = response.get("usage", {})
                total_tokens = usage.get("total_tokens", 0)
                block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)

                parsed_json = json.loads(response_text)
                return response_schema.parse_obj(parsed_json).dict()

            except (OpenAIError, RateLimitError) as e:
                tries += 1
                wait_time = tries * 3
                print(
                    f"Azure OpenAI rate-limit/timeout error: {e}. "
                    f"Retrying in {wait_time}s... (Attempt {tries}/{max_retries})"
                )
                time.sleep(wait_time)
            except Exception as e:
                print(f"Azure OpenAI error: {e}")
                break

        return {}
