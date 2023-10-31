import argparse
import os
import ray
from tqdm import tqdm
import math

from marker.convert import convert_single_pdf
from marker.segmentation import load_layout_model
from marker.cleaners.equations import load_nougat_model
from marker.settings import settings


@ray.remote(num_cpus=settings.RAY_CORES_PER_WORKER)
def process_single_pdf(fname, out_folder, nougat_model, layout_model):
    out_filename = fname.rsplit(".", 1)[0] + ".md"
    out_filename = os.path.join(out_folder, os.path.basename(out_filename))
    if os.path.exists(out_filename):
        return
    try:
        full_text = convert_single_pdf(fname, layout_model, nougat_model)
        with open(out_filename, "w+") as f:
            f.write(full_text)
    except Exception as e:
        print(f"Error converting {fname}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert multiple pdfs to markdown.")
    parser.add_argument("in_folder", help="Input folder with pdfs.")
    parser.add_argument("out_folder", help="Output folder")
    parser.add_argument("--chunk_idx", type=int, default=0, help="Chunk index to convert")
    parser.add_argument("--num_chunks", type=int, default=1, help="Number of chunks being processed in parallel")
    parser.add_argument("--max", type=int, default=None, help="Maximum number of pdfs to convert")
    parser.add_argument("--workers", type=int, default=5, help="Number of worker processes to use")

    args = parser.parse_args()

    in_folder = args.in_folder
    out_folder = args.out_folder
    files = [os.path.join(in_folder, f) for f in os.listdir(in_folder) if f.endswith(".pdf")]
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

    total_processes = min(len(files), args.workers)

    ray.init(
        num_cpus=total_processes,
        storage=settings.RAY_CACHE_PATH,
        _temp_dir=settings.RAY_CACHE_PATH,
        dashboard_host=settings.RAY_DASHBOARD_HOST
    )

    nougat_model = load_nougat_model()
    layoutlm_model = load_layout_model()

    nougat_ref = ray.put(nougat_model)
    layoutlm_ref = ray.put(layoutlm_model)

    print(f"Converting {len(files_to_convert)} pdfs with {total_processes} processes, and storing in {out_folder}")
    futures = [process_single_pdf.remote(filename, out_folder, nougat_ref, layoutlm_ref) for filename in files_to_convert]

    # Run all ray conversion tasks
    progress_bar = tqdm(total=len(futures))
    while len(futures) > 0:
        finished, futures = ray.wait(
            futures, timeout=7.0
        )
        finished_lst = ray.get(finished)
        progress_bar.update(len(finished_lst))

    # Shutdown ray to free resources
    ray.shutdown()