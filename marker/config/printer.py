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
    def parse_args(self, ctx, args):
        # If '-l' is in the arguments, handle it and exit
        if '-l' in args:
            base_classes = [BaseBuilder, BaseProcessor, BaseConverter]
            for base in base_classes:
                subclasses = find_subclasses(base)
                for class_name, class_type in subclasses.items():
                    doc = class_type.__doc__
                    if doc:
                        click.echo(f"{class_name}: {doc}")
            ctx.exit()
        super().parse_args(ctx, args)
