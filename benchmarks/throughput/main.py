import os
import tempfile
import time
from multiprocessing import get_context
from concurrent.futures import ProcessPoolExecutor
import torch

import click
import pypdfium2 as pdfium
from tqdm import tqdm

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
import datasets


def get_next_pdf(ds: datasets.Dataset, i: int):
    while True:
        pdf = ds[i]["pdf"]
        filename = ds[i]["filename"]
        if pdf and filename.endswith(".pdf"):
            return pdf, i
        i += 1
        if i >= len(ds):
            i = 0


def single_batch(batch_size: int, format_lines: bool, num_threads: int):
    torch.set_num_threads(num_threads)
    ds = datasets.load_dataset("datalab-to/pdfs", split="train")
    model_dict = create_model_dict()
    torch.cuda.reset_peak_memory_stats()

    times = []
    i = 0
    pages = 0
    for _ in range(batch_size):
        pdf, i = get_next_pdf(ds, i)
        pdf_doc = pdfium.PdfDocument(pdf)
        page_count = len(pdf_doc)
        pdf_doc.close()
        pages += page_count

        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(pdf)
            f.flush()
            block_converter = PdfConverter(
                artifact_dict=model_dict,
                config={
                    "disable_tqdm": True,
                    "format_lines": format_lines,
                },
            )
            start = time.time()
            block_converter(f.name)

            total = time.time() - start
            times.append(total)

    max_gpu_vram = torch.cuda.max_memory_allocated() / 1024**3
    return sum(times), max_gpu_vram, pages


@click.command(help="Benchmark PDF to MD conversion throughput.")
@click.option("--workers", default=1, help="Number of workers to use.")
@click.option("--batch_size", default=1, help="Batch size for inference.")
@click.option("--format_lines", is_flag=True, help="Format lines in the output.")
def main(workers: int, batch_size: int, format_lines: bool):
    total_cpus = os.cpu_count()
    start = time.time()
    with ProcessPoolExecutor(
        max_workers=workers, mp_context=get_context("spawn")
    ) as executor:
        cpus_per_worker = max(2, total_cpus // workers)
        futures = [
            executor.submit(single_batch, batch_size, format_lines, cpus_per_worker)
            for _ in range(workers)
        ]
        all_times = []
        vrams = []
        page_count = 0
        for future in tqdm(futures, desc="Running marker workers..."):
            times, gpu_vram, pages = future.result()
            all_times.append(times)
            vrams.append(gpu_vram)
            page_count += pages

    end = time.time() - start

    print(f"Average time per worker: {sum(all_times) / len(all_times)}")
    print(f"Max time per worker: {max(all_times)}")
    print(f"Max GPU VRAM: {max(vrams)}")
    print(f"Total pages: {page_count}")
    print(f"Total GPU VRAM: {sum(vrams)}")
    print(f"End to end time (counting model loading), all processes: {end}")
    print(f"Time per page: {end / page_count:.2f}")


if __name__ == "__main__":
    main()
