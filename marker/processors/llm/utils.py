import json
import time

import PIL
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from google.api_core.exceptions import ResourceExhausted


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
            image: PIL.Image.Image,
            response_schema: content.Schema,
            max_retries: int = 3,
            timeout: int = 60
    ):
        tries = 0
        while tries < max_retries:
            try:
                responses = self.model.generate_content(
                    [prompt, image],
                    stream=False,
                    generation_config={
                        "temperature": 0,
                        "response_schema": response_schema,
                        "response_mime_type": "application/json",
                    },
                    request_options={'timeout': timeout}
                )
                output = responses.candidates[0].content.parts[0].text
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