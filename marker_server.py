import argparse
import asyncio
import os

import requests
import uvicorn
from starlette.responses import HTMLResponse

os.environ["PDFTEXT_CPU_WORKERS"] = "1"

import base64
from contextlib import asynccontextmanager
from typing import Optional
import io

from fastapi import FastAPI, Form
from marker.convert import convert_single_pdf
from marker.models import load_all_models

app_data = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    if app.state.LOCAL:
        app_data["models"] = load_all_models()

    yield

    if "models" in app_data:
        del app_data["models"]


app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return HTMLResponse(
"""
<h1>Marker API</h1>
<ul>
    <li><a href="/docs">API Documentation</a></li>
    <li><a href="/local">Run marker locally (post request only)</a></li>
    <li><a href="/remote">Run marker remotely (post request only)</a></li>
</ul>
"""
    )


@app.post("/remote")
async def convert_pdf_remote(
    filepath: str = Form(
        ...,
        description="The path to the PDF file, word document, or powerpoint to convert."
    ),
    max_pages: Optional[int] = Form(
        None,
        description="The maximum number of pages in the document to convert."
    ),
    langs: Optional[str] = Form(
        None,
        description="The optional languages to use if OCR is needed, comma separated.  Must be either the names or codes from https://github.com/VikParuchuri/surya/blob/master/surya/languages.py."
    ),
    force_ocr: bool = Form(
        False,
        description="Force OCR on all pages of the PDF.  Defaults to False.  This can lead to worse results if you have good text in your PDFs (which is true in most cases)."
    ),
    paginate: bool = Form(False,
                          description="Whether to paginate the output.  Defaults to False.  If set to True, each page of the output will be separated by a horizontal rule that contains the page number (2 newlines, {PAGE_NUMBER}, 48 - characters, 2 newlines)."),
    extract_images: bool = Form(True, description="Whether to extract images from the PDF.  Defaults to True.  If set to False, no images will be extracted from the PDF."),
):
    with open(filepath, "rb") as f:
        filedata = f.read()

    filename = os.path.basename(filepath)
    form_data = {
        'file': (filename, filedata, 'application/pdf'),
        'max_pages': (None, max_pages),
        'langs': (None, langs),
        'force_ocr': (None, force_ocr),
        'paginate': (None, paginate),
        'extract_images': (None, extract_images),
    }

    headers = {"X-API-Key": app.state.API_KEY}

    response = requests.post(app.state.DATALAB_URL, files=form_data, headers=headers)
    data = response.json()

    check_url = data["request_check_url"]

    for i in range(300):
        await asyncio.sleep(2)
        response = requests.get(check_url, headers=headers)
        data = response.json()

        if data["status"] == "complete":
            break

    return data


@app.post("/local")
async def convert_pdf_local(
    filepath: str = Form(
        ...,
        description="The path to the PDF file to convert."
    ),
    max_pages: Optional[int] = Form(
        None,
        description="The maximum number of pages in the PDF to convert."
    ),
    langs: Optional[str] = Form(
        None,
        description="The optional languages to use if OCR is needed, comma separated.  Must be either the names or codes from https://github.com/VikParuchuri/surya/blob/master/surya/languages.py."
    ),
    force_ocr: bool = Form(
        False,
        description="Force OCR on all pages of the PDF.  Defaults to False.  This can lead to worse results if you have good text in your PDFs (which is true in most cases)."
    )
):
    try:
        full_text, images, metadata = convert_single_pdf(
            filepath,
            app_data["models"],
            max_pages=max_pages,
            langs=langs,
            ocr_all_pages=force_ocr
        )
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

    encoded = {}
    for k, v in images.items():
        byte_stream = io.BytesIO()
        v.save(byte_stream, format="PNG")
        encoded[k] = base64.b64encode(byte_stream.getvalue()).decode("utf-8")

    return {
        "markdown": full_text,
        "images": encoded,
        "metadata": metadata,
        "success": True
    }


def main():
    parser = argparse.ArgumentParser(description='Convert PDFs to markdown.')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    parser.add_argument('--host', type=str, default="127.0.0.1", help='Host to run the server on')
    parser.add_argument('--api_key', type=str, default=None, help='API key for the Datalab API.  If not specified, API will run locally.')
    parser.add_argument("--datalab_url", type=str, default="https://api.datalab.to/api/v1/marker", help="The URL for the Datalab API")

    args = parser.parse_args()

    app.state.API_KEY = args.api_key
    app.state.LOCAL = args.api_key is None
    app.state.DATALAB_URL = args.datalab_url

    # Run the server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()