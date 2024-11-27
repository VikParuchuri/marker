import click

import uvicorn
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

from marker.config.parser import ConfigParser
from marker.output import text_from_rendered

import base64
from contextlib import asynccontextmanager
from typing import Optional, Annotated
import io

from fastapi import FastAPI, Body
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict

app_data = {}


UPLOAD_DIRECTORY = "./uploads"  # Directory to store uploaded files

# Ensure the upload directory exists
if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app_data["models"] = create_model_dict()

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
    page_range: Annotated[
        Optional[str],
        Field(description="Page range to convert, specify comma separated page numbers or ranges.  Example: 0,5-10,20", example=None)
    ] = None
    languages: Annotated[
        Optional[str],
        Field(description="Comma separated list of languages to use for OCR. Must be either the names or codes from from https://github.com/VikParuchuri/surya/blob/master/surya/languages.py.", example=None)
    ] = None
    force_ocr: Annotated[
        bool,
        Field(
            description="Force OCR on all pages of the PDF.  Defaults to False.  This can lead to worse results if you have good text in your PDFs (which is true in most cases)."
        ),
    ] = False
    paginate_output: Annotated[
        bool,
        Field(
            description="Whether to paginate the output.  Defaults to False.  If set to True, each page of the output will be separated by a horizontal rule that contains the page number (2 newlines, {PAGE_NUMBER}, 48 - characters, 2 newlines)."
        ),
    ] = False
    output_format: Annotated[
        str,
        Field(description="The format to output the text in.  Can be 'markdown', 'json', or 'html'.  Defaults to 'markdown'.")
    ] = "markdown"


@app.post("/marker")
async def convert_pdf(
    params: CommonParams
):
    assert params.output_format in ["markdown", "json", "html"], "Invalid output format"
    try:
        options = params.model_dump()
        config_parser = ConfigParser(options)
        config_dict = config_parser.generate_config_dict()
        config_dict["pdftext_workers"] = 1
        converter = PdfConverter(
            config=config_dict,
            artifact_dict=app_data["models"],
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer()
        )
        rendered = converter(params.filepath)
        text, _, images = text_from_rendered(rendered)
        metadata = rendered.metadata
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
        "format": params.output_format,
        "output": text,
        "images": encoded,
        "metadata": metadata,
        "success": True,
    }


@click.command()
@click.option("--port", type=int, default=8000, help="Port to run the server on")
@click.option("--host", type=str, default="127.0.0.1", help="Host to run the server on")
def main(port: int, host: str):
    # Run the server
    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
