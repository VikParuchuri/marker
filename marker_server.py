import argparse
import asyncio
import os

import requests
import uvicorn
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

os.environ["PDFTEXT_CPU_WORKERS"] = "1"

import base64
from contextlib import asynccontextmanager
from typing import Optional, Annotated
import io

from fastapi import FastAPI, Body, Form, File, UploadFile, HTTPException
from marker.convert import convert_single_pdf
from marker.models import load_all_models

app_data = {}


UPLOAD_DIRECTORY = "./uploads"  # Directory to store uploaded files

# Ensure the upload directory exists
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)


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
    <li><a href="/marker">Run marker (post request only)</a></li>
</ul>
"""
    )


class CommonParams(BaseModel):
    filepath: Annotated[
        Optional[str], Field(description="The path to the PDF file to convert.")
    ]
    max_pages: Annotated[
        Optional[int],
        Field(
            description="The maximum number of pages in the document to convert.",
            example=None,
        ),
    ] = None
    langs: Annotated[
        Optional[str],
        Field(
            description="The optional languages to use if OCR is needed, comma separated.  Must be either the names or codes from from https://github.com/VikParuchuri/surya/blob/master/surya/languages.py.",
            example=None,
        ),
    ] = None
    force_ocr: Annotated[
        bool,
        Field(
            description="Force OCR on all pages of the PDF.  Defaults to False.  This can lead to worse results if you have good text in your PDFs (which is true in most cases)."
        ),
    ] = False
    paginate: Annotated[
        bool,
        Field(
            description="Whether to paginate the output.  Defaults to False.  If set to True, each page of the output will be separated by a horizontal rule that contains the page number (2 newlines, {PAGE_NUMBER}, 48 - characters, 2 newlines)."
        ),
    ] = False
    extract_images: Annotated[
        bool,
        Field(
            description="Whether to extract images from the PDF.  Defaults to True.  If set to False, no images will be extracted from the PDF."
        ),
    ] = True


@app.post("/marker")
async def convert_pdf(params: CommonParams):
    if app.state.LOCAL:
        print(f"Converting {params.filepath} locally.")
        assert all(
            [
                params.extract_images is True,
                params.paginate is False,
            ]
        ), "Local conversion API does not support image extraction or pagination."
        return await convert_pdf_local(params)
    else:
        print(f"Converting {params.filepath} using the Datalab API.")
        return await convert_pdf_remote(params)


@app.post("/marker/upload")
async def convert_pdf_upload(
    max_pages: Optional[int] = Form(default=None),
    langs: Optional[str] = Form(default=None),
    force_ocr: Optional[bool] = Form(default=False),
    paginate: Optional[bool] = Form(default=False),
    extract_images: Optional[bool] = Form(default=True),
    file: UploadFile = File(
        ..., description="The PDF file to convert.", media_type="application/pdf"
    ),
):
    params = CommonParams(
        filepath=None,
        max_pages=max_pages,
        langs=langs,
        force_ocr=force_ocr,
        paginate=paginate,
        extract_images=extract_images,
    )

    print(f"Converting the uploaded PDF file: {file.filename}")
    return await convert_pdf_from_upload(file, params)


async def convert_pdf_from_upload(file: UploadFile, params: CommonParams):
    # Check that the uploaded file is a PDF
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed.")

    try:
        # Save the uploaded file in the ./uploads directory
        upload_path = os.path.join(UPLOAD_DIRECTORY, file.filename)

        with open(upload_path, "wb") as upload_file:
            file_contents = await file.read()
            upload_file.write(file_contents)

        # Proceed with the conversion using the saved file path
        params.filepath = upload_path
        if app.state.LOCAL:
            return await convert_pdf_local(params)
        else:
            return await convert_pdf_remote(params)
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    finally:
        # Clean up the uploaded file after processing
        if os.path.exists(upload_path):
            os.remove(upload_path)


async def convert_pdf_remote(params: CommonParams):
    with open(params.filepath, "rb") as f:
        filedata = f.read()

    filename = os.path.basename(params.filepath)
    form_data = {
        "file": (filename, filedata, "application/pdf"),
        "max_pages": (None, params.max_pages),
        "langs": (None, params.langs),
        "force_ocr": (None, params.force_ocr),
        "paginate": (None, params.paginate),
        "extract_images": (None, params.extract_images),
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


async def convert_pdf_local(params: CommonParams):
    try:
        full_text, images, metadata = convert_single_pdf(
            params.filepath,
            app_data["models"],
            max_pages=params.max_pages,
            langs=params.langs,
            ocr_all_pages=params.force_ocr,
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
        "success": True,
    }


def main():
    parser = argparse.ArgumentParser(description="Convert PDFs to markdown.")
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to run the server on"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host to run the server on"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="API key for the Datalab API.  If not specified, API will run locally.",
    )
    parser.add_argument(
        "--datalab_url",
        type=str,
        default="https://api.datalab.to/api/v1/marker",
        help="The URL for the Datalab API",
    )

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
