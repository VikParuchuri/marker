import argparse
import tempfile
import time
from collections import defaultdict

from tqdm import tqdm

from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.models import load_all_models
from marker.benchmark.scoring import score_text
from marker.extract_text import naive_get_text
import json
import os
import subprocess
import shutil
import fitz as pymupdf
from tabulate import tabulate

configure_logging()


def nougat_prediction(pdf_filename, batch_size=1):
    out_dir = tempfile.mkdtemp()
    subprocess.run(["nougat", pdf_filename, "-o", out_dir, "--no-skipping", "--recompute", "--batchsize", str(batch_size)], check=True)
    md_file = os.listdir(out_dir)[0]
    with open(os.path.join(out_dir, md_file), "r") as f:
        data = f.read()
    shutil.rmtree(out_dir)
    return data


def main():
    parser = argparse.ArgumentParser(description="Benchmark PDF to MD conversion.  Needs source pdfs, and a refernece folder with the correct markdown.")
    parser.add_argument("in_folder", help="Input PDF files")
    parser.add_argument("reference_folder", help="Reference folder with reference markdown files")
    parser.add_argument("out_file", help="Output filename")
    parser.add_argument("--nougat", action="store_true", help="Run nougat and compare", default=False)
    # Nougat batch size 1 uses about as much VRAM as default marker settings
    parser.add_argument("--nougat_batch_size", type=int, default=1, help="Batch size to use for nougat when making predictions.")
    parser.add_argument("--marker_parallel_factor", type=int, default=1, help="How much to multiply default parallel OCR workers and model batch sizes by.")
    parser.add_argument("--md_out_path", type=str, default=None, help="Output path for generated markdown files")
    args = parser.parse_args()

    methods = ["naive", "marker"]
    if args.nougat:
        methods.append("nougat")

    model_lst = load_all_models()

    scores = defaultdict(dict)
    benchmark_files = os.listdir(args.in_folder)
    benchmark_files = [b for b in benchmark_files if b.endswith(".pdf")]
    times = defaultdict(dict)
    pages = defaultdict(int)

    for fname in tqdm(benchmark_files):
        md_filename = fname.rsplit(".", 1)[0] + ".md"

        reference_filename = os.path.join(args.reference_folder, md_filename)
        with open(reference_filename, "r") as f:
            reference = f.read()

        pdf_filename = os.path.join(args.in_folder, fname)
        doc = pymupdf.open(pdf_filename)
        pages[fname] = len(doc)

        for method in methods:
            start = time.time()
            if method == "marker":
                full_text, out_meta = convert_single_pdf(pdf_filename, model_lst, parallel_factor=args.marker_parallel_factor)
            elif method == "nougat":
                full_text = nougat_prediction(pdf_filename, batch_size=args.nougat_batch_size)
            elif method == "naive":
                full_text = naive_get_text(doc)
            else:
                raise ValueError(f"Unknown method {method}")

            times[method][fname] = time.time() - start

            score = score_text(full_text, reference)
            scores[method][fname] = score

            if args.md_out_path:
                md_out_filename = f"{method}_{md_filename}"
                with open(os.path.join(args.md_out_path, md_out_filename), "w+") as f:
                    f.write(full_text)

    total_pages = sum(pages.values())
    with open(args.out_file, "w+") as f:
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

