import os

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1" # Transformers uses .isin for a simple op, which is not supported on MPS

import time

import click

from marker.config.parser import ConfigParser
from marker.config.printer import CustomClickPrinter
from marker.converters.pdf import PdfConverter
from marker.logger import configure_logging
from marker.models import create_model_dict
from marker.output import save_output

configure_logging()


@click.command(cls=CustomClickPrinter, help="Convert a single PDF to markdown.")
@click.argument("fpath", type=str)
@ConfigParser.common_options
def main(fpath: str, **kwargs):
    models = create_model_dict()
    start = time.time()
    config_parser = ConfigParser(kwargs)

    converter = PdfConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer()
    )
    rendered = converter(fpath)
    out_folder = config_parser.get_output_folder(fpath)
    save_output(rendered, out_folder, config_parser.get_base_filename(fpath))

    print(f"Saved markdown to {out_folder}")
    print(f"Total time: {time.time() - start}")


if __name__ == "__main__":
    main()
