import os

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS
os.environ["IN_STREAMLIT"] = "true" # Avoid multiprocessing inside surya
os.environ["PDFTEXT_CPU_WORKERS"] = "1" # Avoid multiprocessing inside pdftext

import pypdfium2 # Needs to be at the top to avoid warnings
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
import traceback
import json

configure_logging()


def worker_init(shared_model):
    if shared_model is None:
        shared_model = load_all_models()

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
        # Skip trying to convert files that don't have a lot of embedded text
        # This can indicate that they were scanned, and not OCRed properly
        # Usually these files are not recent/high-quality
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
            print(f"Empty file: {filepath}.  Could not convert.")
    except Exception as e:
        print(f"Error converting {filepath}: {e}")
        print(traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(description="Convert multiple pdfs to markdown.")
    parser.add_argument("in_folder", help="Input folder with pdfs.")
    parser.add_argument("out_folder", help="Output folder")
    parser.add_argument("--chunk_idx", type=int, default=0, help="Chunk index to convert")
    parser.add_argument("--num_chunks", type=int, default=1, help="Number of chunks being processed in parallel")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of pdfs to convert")
    parser.add_argument("--workers", type=int, default=5, help="Number of worker processes to use")
    parser.add_argument("--metadata_file", type=str, default=None, help="Metadata json file to use for filtering")
    parser.add_argument("--min_length", type=int, default=None, help="Minimum length of pdf to convert")

    args = parser.parse_args()

    in_folder = os.path.abspath(args.in_folder)
    out_folder = os.path.abspath(args.out_folder)
    files = [os.path.join(in_folder, f) for f in os.listdir(in_folder)]
    files = [f for f in files if os.path.isfile(f)]
    os.makedirs(out_folder, exist_ok=True)

    # Handle chunks if we're processing in parallel
    # Ensure we get all files into a chunk
    chunk_size = math.ceil(len(files) / args.num_chunks)
    start_idx = args.chunk_idx * chunk_size
    end_idx = start_idx + chunk_size
    files_to_convert = files[start_idx:end_idx]

    # Limit files converted if needed
    if args.max:
        files_to_convert = files_to_convert[:args.max]

    metadata = {}
    if args.metadata_file:
        metadata_file = os.path.abspath(args.metadata_file)
        with open(metadata_file, "r") as f:
            metadata = json.load(f)

    total_processes = min(len(files_to_convert), args.workers)

    # Dynamically set GPU allocation per task based on GPU ram
    if settings.CUDA:
        tasks_per_gpu = settings.INFERENCE_RAM // settings.VRAM_PER_TASK if settings.CUDA else 0
        total_processes = int(min(tasks_per_gpu, total_processes))
    else:
        total_processes = int(total_processes)

    try:
        mp.set_start_method('spawn') # Required for CUDA, forkserver doesn't work
    except RuntimeError:
        raise RuntimeError("Set start method to spawn twice. This may be a temporary issue with the script. Please try running it again.")

    if settings.TORCH_DEVICE == "mps" or settings.TORCH_DEVICE_MODEL == "mps":
        print("Cannot use MPS with torch multiprocessing share_memory. This will make things less memory efficient. If you want to share memory, you have to use CUDA or CPU.  Set the TORCH_DEVICE environment variable to change the device.")

        model_lst = None
    else:
        model_lst = load_all_models()

        for model in model_lst:
            if model is None:
                continue
            model.share_memory()

    print(f"Converting {len(files_to_convert)} pdfs in chunk {args.chunk_idx + 1}/{args.num_chunks} with {total_processes} processes, and storing in {out_folder}")
    task_args = [(f, out_folder, metadata.get(os.path.basename(f)), args.min_length) for f in files_to_convert]

    with mp.Pool(processes=total_processes, initializer=worker_init, initargs=(model_lst,)) as pool:
        list(tqdm(pool.imap(process_single_pdf, task_args), total=len(task_args), desc="Processing PDFs", unit="pdf"))

        pool._worker_handler.terminate = worker_exit

    # Delete all CUDA tensors
    del model_lst


if __name__ == "__main__":
    main()