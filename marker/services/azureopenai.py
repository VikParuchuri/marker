import time
import json
import base64
from io import BytesIO
from typing import Annotated, List, Union

from openai import AzureOpenAI
from openai.types.chat import ChatCompletion
from openai import RateLimitError, OpenAIError

from PIL import Image
from pydantic import BaseModel

from marker.services import BaseService
from marker.schema.blocks import Block


class MyAzureOpenAIService(BaseService):
    """
    A service that calls Azure OpenAI for ChatCompletion with images + text prompts.
    Uses the new openai.Client() format for compatibility with openai>=1.0.0.
    """

    def __init__(
        self,
        azure_api_key: str,
        azure_base_url: str,
        azure_api_version: str = "2023-03-15-preview",
        azure_deployment_name: str = "gpt-4o",
        max_retries: int = 3,
        timeout: int = 60,
    ):
        self.azure_api_key = azure_api_key
        self.azure_base_url = azure_base_url
        self.azure_api_version = azure_api_version
        self.azure_deployment_name = azure_deployment_name
        self.max_retries = max_retries
        self.timeout = timeout

        # Call parent class's constructor if needed
        super().__init__()

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

    def get_client(self) -> AzureOpenAI:
        """
        Returns an OpenAI client configured for Azure OpenAI.
        """
        return AzureOpenAI(
            api_key=self.azure_api_key,
            azure_endpoint=f"{self.azure_base_url}",
            api_version=self.azure_api_version,
            timeout=self.timeout,
        )

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
                response: ChatCompletion = client.chat.completions.create(
                    model=self.azure_deployment_name,
                    messages=messages,
                )

                response_text = response.choices[0].message.content
                usage = response.usage
                total_tokens = usage.total_tokens if usage else 0
                block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)

                parsed_json = json.loads(response_text)
                return response_schema.model_validate(parsed_json)

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
