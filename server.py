import os
import pypdfium2  # Needs to be at the top to avoid warnings
import argparse
import torch.multiprocessing as mp
from tqdm import tqdm
import math

from marker.convert import convert_single_pdf
from marker.output import markdown_exists, save_markdown
from marker.pdf.utils import find_filetype
from marker.pdf.extract_text import get_length_of_text
from marker.models import load_all_models
from marker.settings import settings
from marker.logger import configure_logging

os.environ["IN_STREAMLIT"] = "true"  # Avoid multiprocessing inside surya
os.environ["PDFTEXT_CPU_WORKERS"] = "1"  # Avoid multiprocessing inside pdftext

configure_logging()

model_refs = None
pool = None


def worker_init(shared_model):
    global model_refs
    model_refs = shared_model


def worker_exit():
    global model_refs
    del model_refs


def process_single_pdf(args):
    filepath, out_folder, metadata, min_length = args

    fname = os.path.basename(filepath)
    if markdown_exists(out_folder, fname):
        return

    try:
        if min_length:
            filetype = find_filetype(filepath)
            if filetype == "other":
                return 0

            length = get_length_of_text(filepath)
            if length < min_length:
                return

        full_text, images, out_metadata = convert_single_pdf(filepath, model_refs, metadata=metadata)
        if len(full_text.strip()) > 0:
            save_markdown(out_folder, fname, full_text, images, out_metadata)
        else:
            print(f"Empty file: {filepath}. Could not convert.")
    except Exception as e:
        print(f"Error converting {filepath}: {e}")
        print(traceback.format_exc())


def init_models_and_workers(workers):
    global model_refs, pool
    model_lst = load_all_models()

    for model in model_lst:
        if model is None:
            continue

        if model.device.type == "mps":
            raise ValueError("Cannot use MPS with torch multiprocessing share_memory. You have to use CUDA or CPU. Set the TORCH_DEVICE environment variable to change the device.")

        model.share_memory()

    model_refs = model_lst

    total_processes = int(workers)
    if settings.CUDA:
        tasks_per_gpu = settings.INFERENCE_RAM // settings.VRAM_PER_TASK if settings.CUDA else 0
        total_processes = int(min(tasks_per_gpu, total_processes))

    mp.set_start_method('spawn')
    pool = mp.Pool(processes=total_processes, initializer=worker_init, initargs=(model_lst,))

def process_pdfs_core(in_folder, out_folder, chunk_idx, num_chunks, max_pdfs, min_length, metadata_file):
    in_folder = os.path.abspath(in_folder)
    out_folder = os.path.abspath(out_folder)

    files = [os.path.join(in_folder, f) for f in os.listdir(in_folder)]
    files = [f for f in files if os.path.isfile(f)]
    os.makedirs(out_folder, exist_ok=True)

    chunk_size = math.ceil(len(files) / num_chunks)
    start_idx = chunk_idx * chunk_size
    end_idx = start_idx + chunk_size
    files_to_convert = files[start_idx:end_idx]

    if max_pdfs:
        files_to_convert = files_to_convert[:max_pdfs]

    metadata = {}
    if metadata_file:
        metadata_file_path = os.path.abspath(metadata_file)
        with open(metadata_file_path, "r") as f:
            metadata = json.load(f)

    task_args = [(f, out_folder, metadata.get(os.path.basename(f)), min_length) for f in files_to_convert]

    try:
        list(tqdm(pool.imap(process_single_pdf, task_args), total=len(task_args), desc="Processing PDFs", unit="pdf"))
        return {"status": "success", "message": f"Processed {len(files_to_convert)} PDFs."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# Server Stuff.
#
#
import base64
import secrets
def rand_string() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(8)).decode()

from pathlib import Path

from pydantic import BaseModel

from typing import Optional
import signal  # Add this import to handle signal
from litestar import Litestar, Controller, post  # Importing Litestar
import traceback
import json
import uvicorn

import os
import shutil

class BaseMarkerCliInput(BaseModel):
    in_folder: str
    out_folder: str 
    chunk_idx: int = 0
    num_chunks : int = 1
    max_pdfs : Optional[int] = None 
    min_length : Optional[int] = None 
    metadata_file : Optional[str] = None




class PDFUploadFormData(BaseModel):
    file: bytes

TMP_DIR = Path("/tmp")
MARKER_TMP_DIR = TMP_DIR / Path("marker")
class PDFProcessor(Controller):
    @post("/process_pdf_upload", media_type="multipart/form-data")
    async def process_pdf_upload_endpoint(data : PDFUploadFormData ) -> str:
        doc_dir = MARKER_TMP_DIR / Path(rand_string())

        # Parse the uploaded file
        pdf_binary = data.file

        input_directory = doc_dir / Path("in")
        output_directory = doc_dir / Path("out")
        
        # Ensure the directories exist
        os.makedirs(input_directory, exist_ok=True)
        os.makedirs(output_directory, exist_ok=True)
        
        # Save the PDF to the output directory
        pdf_filename = os.path.join(input_directory, pdf_file.filename)
        with open(pdf_filename, "wb") as f:
            f.write(pdf_binary.read())
        
        # Process the PDF
        result = process_pdfs_core(input_directory, output_directory, chunk_idx=0, num_chunks=1, max_pdfs=1, min_length=None, metadata_file=None)

        # Read the output markdown file
        # TODO : Fix at some point with tests
        output_filename = os.path.join(out_folder, pdf_file.filename.replace(".pdf", ".md"))
        if not os.path.exists(output_filename):
            return Response({"error": "Output markdown file not found."}, status_code=500)
        with open(output_filename, "r") as f:
            markdown_content = f.read()
        # Cleanup directories
        shutil.rmtree(doc_dir)
        # Return the markdown content as a response
        return markdown_content 

    @post("/process_pdfs_raw_cli")
    async def process_pdfs_endpoint_raw_cli(data: BaseMarkerCliInput) -> None:
        in_folder = data.in_folder
        out_folder = data.out_folder
        chunk_idx = data.chunk_idx
        num_chunks = data.num_chunks
        max_pdfs = data.max_pdfs
        min_length = data.min_length
        metadata_file = data.metadata_file

        result = process_pdfs_core(in_folder, out_folder, chunk_idx, num_chunks, max_pdfs, min_length, metadata_file)
        return result

def start_server():
    app = Litestar(
        route_handlers = [PDFProcessor]
    )

    run_config = uvicorn.Config(app, port=2718, host="0.0.0.0")
    server = uvicorn.Server(run_config)

    init_models_and_workers(workers=5)  # Initialize models and workers with a default worker count of 5
    signal.signal(signal.SIGINT, lambda s, f: shutdown())  # Updated to catch Control-C and run shutdown
    server.run()
    shutdown()


def shutdown():
    global model_refs, pool
    if pool:
        pool.close()
        pool.join()
    del model_refs


if __name__ == "__main__":
    start_server()



