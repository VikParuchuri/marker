import json
import os
from typing import Dict

import click

from marker.renderers.html import HTMLRenderer
from marker.settings import settings
from marker.util import parse_range_str, strings_to_classes, classes_to_strings
from marker.renderers.markdown import MarkdownRenderer
from marker.renderers.json import JSONRenderer


class ConfigParser:
    def __init__(self, cli_options: dict):
        self.cli_options = cli_options

    @staticmethod
    def common_options(fn):
        fn = click.option("--output_dir", type=click.Path(exists=False), required=False, default=settings.OUTPUT_DIR,
                          help="Directory to save output.")(fn)
        fn = click.option('--debug', '-d', is_flag=True, help='Enable debug mode.')(fn)
        fn = click.option("--output_format", type=click.Choice(["markdown", "json", "html"]), default="markdown",
                          help="Format to output results in.")(fn)
        fn = click.option("--page_range", type=str, default=None,
                          help="Page range to convert, specify comma separated page numbers or ranges.  Example: 0,5-10,20")(
            fn)
        fn = click.option("--force_ocr", is_flag=True, help="Force OCR on the whole document.")(fn)
        fn = click.option("--processors", type=str, default=None,
                          help="Comma separated list of processors to use.  Must use full module path.")(fn)
        fn = click.option("--config_json", type=str, default=None,
                          help="Path to JSON file with additional configuration.")(fn)
        fn = click.option("--languages", type=str, default=None, help="Comma separated list of languages to use for OCR.")(fn)
        fn = click.option("--disable_multiprocessing", is_flag=True, default=False, help="Disable multiprocessing.")(fn)
        fn = click.option("--paginate_output", is_flag=True, default=False, help="Paginate output.")(fn)
        fn = click.option("--disable_image_extraction", is_flag=True, default=False, help="Disable image extraction.")(fn)
        return fn

    def generate_config_dict(self) -> Dict[str, any]:
        config = {}
        output_dir = self.cli_options.get("output_dir", settings.OUTPUT_DIR)
        for k, v in self.cli_options.items():
            match k:
                case "debug":
                    if v:
                        config["debug_pdf_images"] = True
                        config["debug_layout_images"] = True
                        config["debug_json"] = True
                        config["debug_data_folder"] = output_dir
                case "page_range":
                    if v:
                        config["page_range"] = parse_range_str(v)
                case "force_ocr":
                    if v:
                        config["force_ocr"] = True
                case "languages":
                    if v:
                        config["languages"] = v.split(",")
                case "config_json":
                    if v:
                        with open(v, "r") as f:
                            config.update(json.load(f))
                case "disable_multiprocessing":
                    if v:
                        config["pdftext_workers"] = 1
                case "paginate_output":
                    if v:
                        config["paginate_output"] = True
                case "disable_image_extraction":
                    if v:
                        config["extract_images"] = False
        return config

    def get_renderer(self):
        match self.cli_options["output_format"]:
            case "json":
                r = JSONRenderer
            case "markdown":
                r = MarkdownRenderer
            case "html":
                r = HTMLRenderer
            case _:
                raise ValueError("Invalid output format")
        return classes_to_strings([r])[0]

    def get_processors(self):
        processors = self.cli_options.get("processors", None)
        if processors is not None:
            processors = processors.split(",")
            for p in processors:
                try:
                    strings_to_classes([p])
                except Exception as e:
                    print(f"Error loading processor: {p} with error: {e}")
                    raise

        return processors

    def get_output_folder(self, filepath: str):
        output_dir = self.cli_options.get("output_dir", settings.OUTPUT_DIR)
        fname_base = os.path.splitext(os.path.basename(filepath))[0]
        output_dir = os.path.join(output_dir, fname_base)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def get_base_filename(self, filepath: str):
        basename = os.path.basename(filepath)
        return os.path.splitext(basename)[0]
