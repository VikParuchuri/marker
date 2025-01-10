import json
import time
from typing import List

import PIL
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from google.api_core.exceptions import ResourceExhausted

from marker.schema.blocks import Block


class GoogleModel:
    def __init__(self, api_key: str, model_name: str):
        if api_key is None:
            raise ValueError("Google API key is not set")

        self.api_key = api_key
        self.model_name = model_name
        self.model = self.configure_google_model()

    def configure_google_model(self):
        genai.configure(api_key=self.api_key)
        return genai.GenerativeModel(self.model_name)

    def generate_response(
            self,
            prompt: str,
            image: PIL.Image.Image | List[PIL.Image.Image],
            block: Block,
            response_schema: content.Schema,
            max_retries: int = 3,
            timeout: int = 60
    ):
        if not isinstance(image, list):
            image = [image]
        tries = 0
        while tries < max_retries:
            try:
                responses = self.model.generate_content(
                    image + [prompt], # According to gemini docs, it performs better if the image is the first element
                    stream=False,
                    generation_config={
                        "temperature": 0,
                        "response_schema": response_schema,
                        "response_mime_type": "application/json",
                    },
                    request_options={'timeout': timeout}
                )
                output = responses.candidates[0].content.parts[0].text
                total_tokens = responses.usage_metadata.total_token_count
                block.update_metadata(llm_tokens_used=total_tokens, llm_request_count=1)
                return json.loads(output)
            except ResourceExhausted as e:
                tries += 1
                wait_time = tries * 3
                print(f"ResourceExhausted: {e}. Retrying in {wait_time} seconds... (Attempt {tries}/{max_retries})")
                time.sleep(wait_time)
            except Exception as e:
                print(e)
                break

        return {}