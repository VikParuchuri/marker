from collections import Counter
from openai import OpenAI
import os
import json
from typing import List
import base64
import tempfile

from marker.schema.page import Page
import fitz
from PIL import Image
from pdf2image import convert_from_path
import pytesseract

from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException
from marker.settings import settings

# Ensure the results are deterministic
DetectorFactory.seed = 0

def detect_language_text(text):
    try:
        # Detect the language
        language = detect(text)
    except LangDetectException:
        # If detection fails, return 'unknown'
        language = 'unknown'
    return language

api_key = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=api_key)

text_prompt = '''
You are a bot who identifies language of a given text. If text is gibberish or encoded, do not return any language (return empty string).
Response format: json object with key: "language", value:"ISO 639-1 code of language."
Here's the text: 
'''

image_prompt = '''
You are a powerful language model with vision capabilities. Your task is to analyze the provided image, and then determine the language of the text in it.

Provide the result in the following JSON format:
{
  "language": "<detected_language_code>",
}

Here is the image for analysis:
'''

def detect_language_llm(text, prompt=text_prompt):
    if len(text.split()) > 1000:
        text=" ".join(text.split()[0:1000])
    try:
        print("Detecting language...")
        response = client.chat.completions.create(
            # model="gpt-4",
            model="gpt-3.5-turbo-0125",
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt + text
                }
            ],
            response_format={"type": "json_object"},
        )

        llm_response = response.choices[0].message.content
        language=json.loads(llm_response)["language"]
    
    except:
        print("Error while detecting language")
        language = ""

    
    return language        

def detect_language_page(image, prompt=image_prompt):
    try:
        base64_image = encode_image(image)
        print("Detecting language.")
        response = client.chat.completions.create(
            model = "gpt-4o-mini",
            messages = [
                {
                    "role":"user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
        )
        llm_response = response.choices[0].message.content
        print(llm_response)
        language=json.loads(llm_response)["language"]

    except Exception as e:
        print("Error while detecting language.")
        language = "en"

    return language

def detect_language_ocr(pdf_path):
    try:
        print("Detecting language using OCR")
        pdf_document = fitz.open(pdf_path)
        n_pages = pdf_document.page_count

        results = []
        for page_number in range(min(3, n_pages)):
            page = pdf_document.load_page(page_number)  # Page numbers are 0-indexed in PyMuPDF
            pix = page.get_pixmap()

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp_image_file:
                image_path = temp_image_file.name
                pix.save(image_path)

            # language = detect_language_page(image_path)

            # results.append(language)

            text = extract_text_from_image(image_path)
            result = detect_language_text(text)
            results.append(result)

            # Clean up the temporary image file
            os.remove(image_path)

    except Exception as e:
        print("failed ocr language detection",e)
        return ["en"]

    return results

def extract_text_from_image(image_path):
    """
    Extract text from an image using OCR.

    Parameters:
    image_path (str): The path to the image file.

    Returns:
    str: The text extracted from the image.
    """
    try:
        image = Image.open(image_path)
        text = pytesseract.image_to_string(image, lang='eng+hin+ori')
        return text
    except Exception as e:
        print(f"An error occurred while OCR language detection: {e}")
        return ""

def get_text(pages: List[Page]):
    full_text = ""
    for page in pages:
        full_text += page.prelim_text
    return full_text.strip()

# Function to encode the image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
    
def pdf_page_to_image(pdf_path, page_number):
    images = convert_from_path(pdf_path, first_page=page_number, last_page=page_number)
    return images[0]

def keep_most_frequent_element(lst):
    if not lst:
        return lst
    counter = Counter(lst)
    most_common_element, _ = counter.most_common(1)[0]
    return [most_common_element]