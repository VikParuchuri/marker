import tempfile
import time
from collections import defaultdict

import click
from tqdm import tqdm
import pypdfium2 as pdfium

from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.logger import configure_logging
from marker.models import create_model_dict
from pdftext.extraction import plain_text_output
import json
import os
import subprocess
import shutil
from tabulate import tabulate

from marker.settings import settings
from scoring import score_text

configure_logging()


def nougat_prediction(pdf_filename, batch_size=1):
    out_dir = tempfile.mkdtemp()
    subprocess.run(["nougat", pdf_filename, "-o", out_dir, "--no-skipping", "--recompute", "--batchsize", str(batch_size)], check=True)
    md_file = os.listdir(out_dir)[0]
    with open(os.path.join(out_dir, md_file), "r") as f:
        data = f.read()
    shutil.rmtree(out_dir)
    return data

@click.command(help="Benchmark PDF to MD conversion.")
@click.argument("in_folder", type=str)
@click.argument("reference_folder", type=str)
@click.argument("out_file", type=str)
@click.option("--nougat", is_flag=True, help="Run nougat and compare")
@click.option("--md_out_path", type=str, default=None, help="Output path for generated markdown files")
def main(in_folder: str, reference_folder: str, out_file: str, nougat: bool, md_out_path: str):
    methods = ["marker"]
    if nougat:
        methods.append("nougat")

    model_dict = create_model_dict()

    scores = defaultdict(dict)
    benchmark_files = os.listdir(in_folder)
    benchmark_files = [b for b in benchmark_files if b.endswith(".pdf")]
    times = defaultdict(dict)
    pages = defaultdict(int)

    for idx, fname in tqdm(enumerate(benchmark_files)):
        md_filename = fname.rsplit(".", 1)[0] + ".md"

        reference_filename = os.path.join(reference_folder, md_filename)
        with open(reference_filename, "r") as f:
            reference = f.read()

        pdf_filename = os.path.join(in_folder, fname)
        doc = pdfium.PdfDocument(pdf_filename)
        pages[fname] = len(doc)

        config_parser = ConfigParser({"output_format": "markdown"})
        for method in methods:
            start = time.time()
            if method == "marker":
                converter = PdfConverter(
                    config=config_parser.generate_config_dict(),
                    artifact_dict=model_dict,
                    processor_list=None,
                    renderer=config_parser.get_renderer()
                )
                full_text = converter(pdf_filename).markdown
            elif method == "nougat":
                full_text = nougat_prediction(pdf_filename, batch_size=1)
            elif method == "naive":
                full_text = plain_text_output(doc, workers=1)
            else:
                raise ValueError(f"Unknown method {method}")

            times[method][fname] = time.time() - start

            score = score_text(full_text, reference)
            scores[method][fname] = score

            if md_out_path:
                md_out_filename = f"{method}_{md_filename}"
                with open(os.path.join(md_out_path, md_out_filename), "w+") as f:
                    f.write(full_text)

    total_pages = sum(pages.values())
    with open(out_file, "w+") as f:
        write_data = defaultdict(dict)
        for method in methods:
            total_time = sum(times[method].values())
            file_stats = {
                fname:
                {
                    "time": times[method][fname],
                    "score": scores[method][fname],
                    "pages": pages[fname]
                }

                for fname in benchmark_files
            }
            write_data[method] = {
                "files": file_stats,
                "avg_score": sum(scores[method].values()) / len(scores[method]),
                "time_per_page": total_time / total_pages,
                "time_per_doc": total_time / len(scores[method])
            }

        json.dump(write_data, f, indent=4)

    summary_table = []
    score_table = []
    score_headers = benchmark_files
    for method in methods:
        summary_table.append([method, write_data[method]["avg_score"], write_data[method]["time_per_page"], write_data[method]["time_per_doc"]])
        score_table.append([method, *[write_data[method]["files"][h]["score"] for h in score_headers]])

    print(tabulate(summary_table, headers=["Method", "Average Score", "Time per page", "Time per document"]))
    print("")
    print("Scores by file")
    print(tabulate(score_table, headers=["Method", *score_headers]))


if __name__ == "__main__":
    main()

