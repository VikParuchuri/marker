import json
from PIL import Image
import google.generativeai as genai
from google.ai.generativelanguage_v1beta.types import content
from marker.settings import settings

prompt = """
You're an expert document analyst who is good at turning tables in documents into HTML.  Analyze the provided image, and convert it to a faithful HTML representation.
 
Guidelines:
- Keep the HTML simple and concise.
- Only include the <table> tag and contents.
- Only use <table>, <tr>, and <td> tags.  Only use the colspan and rowspan attributes if necessary.  Do not use <tbody>, <thead>, or <th> tags.
- Make sure the table is as faithful to the image as possible with the given tags.

**Instructions**
1. Analyze the image, and determine the table structure.
2. Convert the table image to HTML, following the guidelines above.
3. Output only the HTML for the table, starting with the <table> tag and ending with the </table> tag.
""".strip()

genai.configure(api_key=settings.GOOGLE_API_KEY)

def gemini_table_rec(image: Image.Image):
    schema = content.Schema(
        type=content.Type.OBJECT,
        required=["table_html"],
        properties={
            "table_html": content.Schema(
                type=content.Type.STRING,
            )
        }
    )

    model = genai.GenerativeModel("gemini-2.0-flash")

    responses = model.generate_content(
        [image, prompt],  # According to gemini docs, it performs better if the image is the first element
        stream=False,
        generation_config={
            "temperature": 0,
            "response_schema": schema,
            "response_mime_type": "application/json",
        },
        request_options={'timeout': 60}
    )

    output = responses.candidates[0].content.parts[0].text
    return json.loads(output)["table_html"]