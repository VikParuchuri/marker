import argparse
import os

from marker.convert import convert_single_pdf
from marker.logger import configure_logging
from marker.models import load_all_models

from marker.output import save_markdown

configure_logging()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="PDF file to parse")
    parser.add_argument("output", help="Output base folder path")
    parser.add_argument("--max_pages", type=int, default=None, help="Maximum number of pages to parse")
    parser.add_argument("--parallel_factor", type=int, default=1, help="How much to multiply default parallel OCR workers and model batch sizes by.")
    parser.add_argument("--langs", type=str, help="Languages to use for OCR, comma separated", default=None)
    args = parser.parse_args()

    langs = args.langs.split(",") if args.langs else None

    fname = args.filename
    model_lst = load_all_models()
    full_text, images, out_meta = convert_single_pdf(fname, model_lst, max_pages=args.max_pages, parallel_factor=args.parallel_factor, langs=langs)

    fname = os.path.basename(fname)
    subfolder_path = save_markdown(args.output, fname, full_text, images, out_meta)

    print(f"Saved markdown to the {subfolder_path} folder")


if __name__ == "__main__":
    main()
