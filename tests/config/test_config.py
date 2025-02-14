import sys
from contextlib import suppress
import click

from marker.config.printer import CustomClickPrinter
from marker.config.crawler import crawler
from marker.config.parser import ConfigParser


def capture_kwargs(argv):
    command = click.command(cls=CustomClickPrinter)
    captured_kwargs = {}

    def parse_args(**kwargs):
        captured_kwargs.update(kwargs)
        return kwargs

    original_argv = sys.argv
    sys.argv = argv
    try:
        with suppress(SystemExit):
            command(ConfigParser.common_options(parse_args))()
    finally:
        sys.argv = original_argv

    return captured_kwargs


def test_config_parser():
    sys.argv = ['test', '--disable_multiprocessing', '--output_dir', 'output_dir', "--height_tolerance", "0.5"]
    kwargs = capture_kwargs(sys.argv)
    parser = ConfigParser(kwargs)
    config_dict = parser.generate_config_dict()

    # Validate kwarg capturing
    assert kwargs["disable_multiprocessing"] == True
    assert kwargs["output_dir"] == "output_dir"

    assert config_dict["pdftext_workers"] == 1 # disabling multiprocessing does this
    assert config_dict["height_tolerance"] == 0.5
    assert "output_dir" not in config_dict # This is not a config key

def test_config_none():
    kwargs = capture_kwargs(['test'])

    for key in crawler.attr_set:
        assert kwargs.get(key) is None
