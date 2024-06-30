import pypdfium2 # Needs to be at the top to avoid warnings
import os
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # For some reason, transformers decided to use .isin for a simple op, which is not supported on MPS

import argparse
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
    parser.add_argument("--start_page", type=int, default=None, help="Page to start processing at")
    parser.add_argument("--langs", type=str, help="Languages to use for OCR, comma separated", default=None)
    parser.add_argument("--batch_multiplier", type=int, default=2, help="How much to increase batch sizes")
    args = parser.parse_args()

    langs = args.langs.split(",") if args.langs else None

    fname = args.filename
    model_lst = load_all_models()
    full_text, images, out_meta = convert_single_pdf(fname, model_lst, max_pages=args.max_pages, langs=langs, batch_multiplier=args.batch_multiplier, start_page=args.start_page)

    fname = os.path.basename(fname)
    subfolder_path = save_markdown(args.output, fname, full_text, images, out_meta)

    print(f"Saved markdown to the {subfolder_path} folder")


if __name__ == "__main__":
    main()
