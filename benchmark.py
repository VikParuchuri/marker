import argparse
import tempfile
import time

from tqdm import tqdm

from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.segmentation import load_layout_model
from marker.cleaners.equations import load_nougat_model
from marker.benchmark.scoring import score_text
import json
import os
import subprocess

configure_logging()


def nougat_prediction(pdf_filename):
    out_dir = tempfile.mkdtemp()
    # No skipping avoids failure detection so we attempt to convert the full doc
    # Batch size 1 is to compare to single-threaded marker
    subprocess.run(["nougat", pdf_filename, "-o", "/tmp/nougat", "--no-skipping", "--batchsize", "1"], check=True)
    md_file = os.listdir(out_dir)[0]
    with open(os.path.join(out_dir, md_file), "r") as f:
        data = f.read()
    os.unlink(out_dir)
    return data


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark PDF to MD conversion.  Needs source pdfs, and a refernece folder with the correct markdown.")
    parser.add_argument("in_folder", help="Input PDF files")
    parser.add_argument("reference_folder", help="Reference folder with reference markdown files")
    parser.add_argument("out_file", help="Output filename")
    parser.add_argument("--nougat", action="store_true", help="Run nougat and compare", default=False)
    args = parser.parse_args()

    layoutlm_model = load_layout_model()
    nougat_model = load_nougat_model()

    marker_scores = {}
    marker_time = 0
    nougat_scores = {}
    nougat_time = 0
    for fname in tqdm(os.listdir(args.in_folder)):
        pdf_filename = os.path.join(args.in_folder, fname)
        start = time.time()
        full_text, out_meta = convert_single_pdf(pdf_filename, layoutlm_model, nougat_model)
        marker_time += time.time() - start

        reference_filename = os.path.join(args.reference_folder, fname.rsplit(".", 1)[0] + ".md")
        with open(reference_filename, "r") as f:
            reference = f.read()

        score = score_text(full_text, reference)
        marker_scores[fname] = score

        if args.nougat:
            start = time.time()
            nougat_text = nougat_prediction(pdf_filename)
            nougat_time += time.time() - start

            score = score_text(nougat_text, reference)
            nougat_scores[fname] = score

    with open(args.out_file, "w+") as f:
        write_data = {
            "marker": {
                "avg_score": sum(marker_scores.values()) / len(marker_scores),
                "scores": marker_scores,
                "time_per_doc": marker_time / len(marker_scores)
            }
        }

        if args.nougat:
            write_data["nougat"] = {
                "avg_score": sum(nougat_scores.values()) / len(nougat_scores),
                "scores": nougat_scores,
                "time_per_doc": nougat_time / len(nougat_scores)
            }

        json.dump(write_data, f, indent=4)

    print(write_data)
