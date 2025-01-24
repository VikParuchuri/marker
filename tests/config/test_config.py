import sys
from contextlib import suppress
from marker.config.parser import ConfigParser

import click

from marker.config.printer import CustomClickPrinter


def test_config_parser():
    command = click.command(cls=CustomClickPrinter)
    captured_kwargs = {}

    def parse_args(**kwargs):
        captured_kwargs.update(kwargs)
        return kwargs

    original_argv = sys.argv
    sys.argv = ['test', '--disable_multiprocessing', '--output_dir', 'output_dir', "--height_tolerance", "0.5"]
    try:
        with suppress(SystemExit):
            command(ConfigParser.common_options(parse_args))()
    finally:
        sys.argv = original_argv

    kwargs = captured_kwargs
    parser = ConfigParser(kwargs)
    config_dict = parser.generate_config_dict()

    # Validate kwarg capturing
    assert captured_kwargs["disable_multiprocessing"] == True
    assert captured_kwargs["output_dir"] == "output_dir"

    assert config_dict["pdftext_workers"] == 1 # disabling multiprocessing does this
    assert config_dict["height_tolerance"] == 0.5
    assert "output_dir" not in config_dict # This is not a config key