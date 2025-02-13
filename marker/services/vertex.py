from typing import Annotated

from google import genai

from marker.services.gemini import BaseGeminiService

class GoogleVertexService(BaseGeminiService):
    vertex_project_id: Annotated[
        str,
        "Google Cloud Project ID for Vertex AI.",
    ] = None
    vertex_location: Annotated[
        str,
        "Google Cloud Location for Vertex AI.",
    ] = "us-central1"
    gemini_model_name: Annotated[
        str,
        "The name of the Google model to use for the service."
    ] = "gemini-1.5-flash-002"

    def get_google_client(self, timeout: int = 60):
        return genai.Client(
            vertexai=True,
            project=self.vertex_project_id,
            location=self.vertex_location,
            http_options={"timeout": timeout * 1000} # Convert to milliseconds
        )