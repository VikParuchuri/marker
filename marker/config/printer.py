import importlib
import inspect
import pkgutil

import click

from marker.builders import BaseBuilder
from marker.converters import BaseConverter
from marker.processors import BaseProcessor


def find_subclasses(base_class):
    """
    Dynamically find all subclasses of a base class in the module where the base class is defined
    and its submodules.
    """
    subclasses = {}
    module_name = base_class.__module__
    package = importlib.import_module(module_name)
    if hasattr(package, '__path__'):
        for _, module_name, _ in pkgutil.walk_packages(package.__path__, module_name + "."):
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, base_class) and obj is not base_class:
                        subclasses[name] = obj
            except ImportError:
                pass
    return subclasses


class CustomClickPrinter(click.Command):
    def get_help(self, ctx):
        additional_help = (
            "\n\nTip: Use 'config --help' to display all the attributes of the Builders, Processors, and Converters in Marker."
        )
        help_text = super().get_help(ctx)
        help_text = help_text + additional_help
        click.echo(help_text)

    def parse_args(self, ctx, args):
        if 'config' in args and '--help' in args:
            click.echo("Here is a list of all the Builders, Processors, and Converters in Marker along with their attributes:")
            base_classes = [BaseBuilder, BaseProcessor, BaseConverter]
            for base in base_classes:
                click.echo(f"{base.__name__.removeprefix('Base')}s:\n")

                subclasses = find_subclasses(base)
                for class_name, class_type in subclasses.items():
                    doc = class_type.__doc__
                    if doc and "Attributes:" in doc:
                        click.echo(f"  {class_name}: {doc}")
            ctx.exit()
        super().parse_args(ctx, args)
