import json
import os

from streamlit_ace import st_ace
from pydantic import BaseModel

from marker.converters.extraction import ExtractionConverter
from marker.scripts.common import (
    parse_args,
    load_models,
    get_page_image,
    page_count,
    get_root_class,
)

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["IN_STREAMLIT"] = "true"

from streamlit.runtime.uploaded_file_manager import UploadedFile

import tempfile
from typing import Any, Dict

import streamlit as st

from marker.config.parser import ConfigParser


def extract_data(fname: str, config: dict, schema: str) -> (str, Dict[str, Any], dict):
    pydantic_root: BaseModel = get_root_class(schema)
    json_schema = pydantic_root.model_json_schema()

    config["pdftext_workers"] = 1
    config["page_schema"] = json.dumps(json_schema)
    config_parser = ConfigParser(config)
    config_dict = config_parser.generate_config_dict()

    converter_cls = ExtractionConverter
    converter = converter_cls(
        config=config_dict,
        artifact_dict=model_dict,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer(),
        llm_service=config_parser.get_llm_service(),
    )
    return converter(fname)


st.set_page_config(layout="wide")
col1, col2 = st.columns([0.5, 0.5])

model_dict = load_models()
cli_options = parse_args()

st.markdown("""
# Marker Extraction Demo

This app will let you use marker to do structured extraction.

Warning: This can execute untrusted code entered into the schema panel.
""")

in_file: UploadedFile = st.sidebar.file_uploader(
    "PDF, document, or image file:",
    type=["pdf", "png", "jpg", "jpeg", "gif", "pptx", "docx", "xlsx", "html", "epub"],
)

if in_file is None:
    st.stop()

filetype = in_file.type

with col1:
    page_count = page_count(in_file)
    page_number = st.number_input(
        f"Page number out of {page_count}:", min_value=0, value=0, max_value=page_count
    )
    pil_image = get_page_image(in_file, page_number)
    st.image(pil_image, use_container_width=True)

with col2:
    st.write("Enter pydantic schema here")
    schema = st_ace(
        value="""from pydantic import BaseModel
class Schema(BaseModel):
    pass""",
        language="python",
    )

run_marker = st.sidebar.button("Run Extraction")

use_llm = st.sidebar.checkbox(
    "Use LLM", help="Use LLM for higher quality text", value=False
)
force_ocr = st.sidebar.checkbox("Force OCR", help="Force OCR on all pages", value=False)
strip_existing_ocr = st.sidebar.checkbox(
    "Strip existing OCR",
    help="Strip existing OCR text from the PDF and re-OCR.",
    value=False,
)
format_lines = st.sidebar.checkbox(
    "Format lines",
    help="Format lines in the document with OCR model",
    value=False,
)

if not run_marker:
    st.stop()

# Run Marker
with tempfile.TemporaryDirectory() as tmp_dir:
    temp_pdf = os.path.join(tmp_dir, "temp.pdf")
    with open(temp_pdf, "wb") as f:
        f.write(in_file.getvalue())

    cli_options.update(
        {
            "force_ocr": force_ocr,
            "use_llm": use_llm,
            "strip_existing_ocr": strip_existing_ocr,
            "format_lines": format_lines,
        }
    )
    rendered = extract_data(temp_pdf, cli_options, schema)

with col2:
    st.write("Output JSON")
    st.json(rendered.model_dump())
