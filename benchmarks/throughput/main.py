import time
import torch

import click
import pypdfium2 as pdfium
from tqdm import tqdm

from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict


@click.command(help="Benchmark PDF to MD conversion throughput.")
@click.argument("pdf_path", type=str)
def main(pdf_path):
    print(f"Converting {pdf_path} to markdown...")
    pdf = pdfium.PdfDocument(pdf_path)
    page_count = len(pdf)
    pdf.close()
    model_dict = create_model_dict()
    torch.cuda.reset_peak_memory_stats()

    times = []
    for i in tqdm(range(10), desc="Benchmarking"):
        block_converter = PdfConverter(
            artifact_dict=model_dict,
            config={"disable_tqdm": True}
        )
        start = time.time()
        block_converter(pdf_path)
        total = time.time() - start
        times.append(total)

    max_gpu_vram = torch.cuda.max_memory_allocated() / 1024 ** 3

    print(f"Converted {page_count} pages in {sum(times)/len(times):.2f} seconds.")
    print(f"Max GPU VRAM: {max_gpu_vram:.2f} GB")


if __name__ == "__main__":
    main()