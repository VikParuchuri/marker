import argparse
import os
from typing import Dict, Optional

import ray
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


@ray.remote(num_cpus=settings.RAY_CORES_PER_WORKER, num_gpus=.05 if settings.CUDA else 0)
def process_single_pdf(filepath: str, out_folder: str, model_refs, metadata: Optional[Dict] = None, min_length: Optional[int] = None):
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

    ray.init(
        num_cpus=total_processes,
        num_gpus=1 if settings.CUDA else 0,
        storage=settings.RAY_CACHE_PATH,
        _temp_dir=settings.RAY_CACHE_PATH,
        log_to_driver=settings.DEBUG
    )

    model_lst = load_all_models()
    model_refs = ray.put(model_lst)

    # Dynamically set GPU allocation per task based on GPU ram
    gpu_frac = settings.VRAM_PER_TASK / settings.INFERENCE_RAM if settings.CUDA else 0

    print(f"Converting {len(files_to_convert)} pdfs in chunk {args.chunk_idx + 1}/{args.num_chunks} with {total_processes} processes, and storing in {out_folder}")
    futures = [
        process_single_pdf.options(num_gpus=gpu_frac).remote(
            filepath,
            out_folder,
            model_refs,
            metadata=metadata.get(os.path.basename(filepath)),
            min_length=args.min_length
        ) for filepath in files_to_convert
    ]

    # Run all ray conversion tasks
    progress_bar = tqdm(total=len(futures))
    while len(futures) > 0:
        finished, futures = ray.wait(
            futures, timeout=7.0
        )
        finished_lst = ray.get(finished)
        if isinstance(finished_lst, list):
            progress_bar.update(len(finished_lst))
        else:
            progress_bar.update(1)

    # Shutdown ray to free resources
    ray.shutdown()


if __name__ == "__main__":
    main()