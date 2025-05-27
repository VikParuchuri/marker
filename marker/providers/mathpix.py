from typing import Optional, Dict, Any
import requests
from PIL import Image
import io
import base64

class MathpixProvider:
    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key
        self.api_url = "https://api.mathpix.com/v3/text"
        
    def _encode_image(self, image: Image.Image) -> str:
        """Convert PIL Image to base64 string"""
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode()

    def process_equation(self, image: Image.Image, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process an equation image using Mathpix API
        
        Args:
            image: PIL Image containing the equation
            options: Additional options for Mathpix API
            
        Returns:
            Dict containing the processed equation data
        """
        if options is None:
            options = {}
            
        # Prepare the request
        headers = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            "Content-Type": "application/json"
        }
        
        # Convert image to base64
        image_data = self._encode_image(image)
        
        # Prepare request body
        data = {
            "src": f"data:image/png;base64,{image_data}",
            "formats": ["text", "latex_styled"],
            "data_options": {
                "include_asciimath": True,
                "include_latex": True
            },
            **options
        }
        
        # Make API request
        response = requests.post(self.api_url, headers=headers, json=data)
        response.raise_for_status()
        
        return response.json() 