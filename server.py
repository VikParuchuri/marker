import os
import pypdfium2  # Needs to be at the top to avoid warnings
import argparse
import torch.multiprocessing as mp
from tqdm import tqdm
import math
from litestar import Litestar, post  # Importing Litestar

from marker.convert import convert_single_pdf
from marker.output import markdown_exists, save_markdown
from marker.pdf.utils import find_filetype
from marker.pdf.extract_text import get_length_of_text
from marker.models import load_all_models
from marker.settings import settings
from marker.logger import configure_logging
import traceback
import json
import uvicorn

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


from pydantic import BaseModel

from typing import Optional

class BaseMarkerCliInput(BaseModel):
    in_folder: str
    out_folder: str 
    chunk_idx: int = 0
    num_chunks : int = 1
    max_pdfs : Optional[int] = None 
    min_length : Optional[int] = None 
    metadata_file : str



@post("/process_pdfs")
async def process_pdfs_endpoint(data: BaseMarkerCliInput) -> None:
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
    app = Litestar([process_pdfs_endpoint])

    run_config = uvicorn.Config(app, port=2718, host="0.0.0.0")
    server = uvicorn.Server(run_config)

    init_models_and_workers(workers=5)  # Initialize models and workers with a default worker count of 5

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



