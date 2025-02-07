import json
import time
from io import BytesIO
from typing import List

import PIL
from google import genai
from google.genai import types
from google.genai.errors import APIError
from pydantic import BaseModel

from marker.schema.blocks import Block
from marker.settings import settings


class GoogleModel:
    def __init__(self, api_key: str, model_name: str):
        if api_key is None:
            raise ValueError("Google API key is not set")

        self.api_key = api_key
        self.model_name = model_name

    def get_google_client(self, timeout: int = 60):
        return genai.Client(
            api_key=settings.GOOGLE_API_KEY,
            http_options={"timeout": timeout * 1000} # Convert to milliseconds
        )

    def img_to_bytes(self, img: PIL.Image.Image):
        image_bytes = BytesIO()
        img.save(image_bytes, format="PNG")
        return image_bytes.getvalue()

    def generate_response(
            self,
            prompt: str,
            image: PIL.Image.Image | List[PIL.Image.Image],
            block: Block,
            response_schema: type[BaseModel],
            max_retries: int = 2,
            timeout: int = 60
    ):
        if not isinstance(image, list):
            image = [image]

        client = self.get_google_client(timeout=timeout)
        image_parts = [types.Part.from_bytes(data=self.img_to_bytes(img), mime_type="image/png") for img in image]

        tries = 0
        while tries < max_retries:
            try:
                responses = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=image_parts + [prompt], # According to gemini docs, it performs better if the image is the first element
                    config={
                        "temperature": 0,
                        "response_schema": response_schema,
                        "response_mime_type": "application/json",
                    }
                )
                output = responses.candidates[0].content.parts[0].text
                total_tokens = responses.usage_metadata.total_token_count
                block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)
                return json.loads(output)
            except APIError as e:
                if e.code == 429:
                    # Rate limit exceeded
                    tries += 1
                    wait_time = tries * 3
                    print(f"APIError: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    print(e)
                    break
            except Exception as e:
                print(e)
                break

        return {}