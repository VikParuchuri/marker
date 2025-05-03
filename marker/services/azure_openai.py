import base64
import json
import time
from io import BytesIO
from typing import Annotated, List, Union

from langchain_openai import AzureChatOpenAI
from openai import AzureOpenAI, APITimeoutError, RateLimitError
import PIL
from PIL import Image
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage

from marker.schema.blocks import Block
from marker.services import BaseService


class ImageDescription(BaseModel):
    """Model for image description response."""
    image_description: str = Field(description="Detailed description of the image content. This will be formatted as markdown italic text.")


class AzureOpenAIService(BaseService):
    azure_endpoint: Annotated[
        str,
        "The Azure OpenAI endpoint URL. No trailing slash."
    ] = None
    azure_api_key: Annotated[
        str,
        "The API key to use for the Azure OpenAI service."
    ] = None
    azure_api_version: Annotated[
        str,
        "The Azure OpenAI API version to use."
    ] = "2024-02-01"
    deployment_name: Annotated[
        str,
        "The deployment name for the Azure OpenAI model."
    ] = None

    def image_to_base64(self, image: PIL.Image.Image):
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
                "image_url": {
                    "url": "data:image/webp;base64,{}".format(
                        self.image_to_base64(img)
                    ),
                }
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

        # Set up AzureChatOpenAI client
        llm = AzureChatOpenAI(
            azure_endpoint=self.azure_endpoint,
            azure_deployment=self.deployment_name,
            api_key=self.azure_api_key,
            api_version=self.azure_api_version,
            temperature=0.0,
            request_timeout=timeout,
        )
        
        # Create a structured output wrapper
        structured_llm = llm.with_structured_output(
            ImageDescription,
            include_raw=False
        )
        
        # Create message content with the correct format for LangChain
        # LangChain expects messages with 'role' and 'content'
        # For multimodal content, we need to use a specific format
        message_content = []
        for img in image:
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/webp;base64,{self.image_to_base64(img)}"
                }
            })
        
        # Add the text prompt at the end
        message_content.append({"type": "text", "text": prompt})
        
        # Create a proper LangChain message
        message = HumanMessage(content=message_content)
        
        tries = 0
        while tries < max_retries:
            try:
                # Use the structured output LLM to get a response
                response = structured_llm.invoke([message])
                
                # If successful, return the structured output directly
                block.update_metadata(llm_tokens_used=4000, llm_request_count=1)  # Approximate token usage
                
                # Convert Pydantic model to dict
                result = response.model_dump()
                
                # Ensure compatibility with expected output format
                if hasattr(response_schema, '__annotations__'):
                    # Add missing fields from response_schema if needed
                    for key in response_schema.__annotations__:
                        if key not in result and key != 'image_description':
                            result[key] = ""
                
                return result
                
            except (APITimeoutError, RateLimitError) as e:
                # Rate limit exceeded
                tries += 1
                wait_time = tries * 3
                print(
                    f"Rate limit error: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})"
                )
                time.sleep(wait_time)
            except Exception as e:
                print(f"Error: {str(e)}")
                tries += 1
                if tries < max_retries:
                    wait_time = tries * 2
                    time.sleep(wait_time)
                else:
                    break

        return {}

    def get_client(self) -> AzureOpenAI:
        return AzureOpenAI(
            api_version=self.azure_api_version,
            azure_endpoint=self.azure_endpoint,
            api_key=self.azure_api_key,
        ) 