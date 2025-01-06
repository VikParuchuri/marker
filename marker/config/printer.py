import importlib
import inspect
import pkgutil
from typing import Annotated, Optional, Type, get_args, get_origin

import click

from marker.builders import BaseBuilder
from marker.converters import BaseConverter
from marker.processors import BaseProcessor
from marker.providers import BaseProvider
from marker.renderers import BaseRenderer


def format_type(t: Type) -> str:
    """Format a typing type like Optional[int] into a readable string."""

    if get_origin(t):  # Handle Optional and types with origins separately
        return f"{t}".removeprefix('typing.')
    else:  # Regular types like int, str
        return t.__name__


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
        display_help = 'config' in args and '--help' in args
        if display_help:
            click.echo("Here is a list of all the Builders, Processors, Converters and Renderers in Marker along with their attributes:")

        base_classes = [BaseBuilder, BaseProcessor, BaseConverter, BaseProvider, BaseRenderer]
        for base in base_classes:
            if display_help:
                click.echo(f"{base.__name__.removeprefix('Base')}s:")

            subclasses = find_subclasses(base)
            for class_name, class_type in subclasses.items():
                doc = class_type.__doc__ or ""
                if display_help and doc and len(class_type.__annotations__):
                    click.echo(f"\n  {class_name}: {doc}")
                    click.echo(" " * 4 + "Attributes:")
                for attr, attr_type in class_type.__annotations__.items():
                    if get_origin(attr_type) is Annotated:
                        base_attr_type = get_args(attr_type)[0]
                        default = getattr(class_type, attr)
                        default_help_str = ""
                        if all('Default' not in desc for desc in attr_type.__metadata__):
                            default_help_str = f"Default is {default}."
                        if display_help:
                            click.echo(" " * 8 + f"{attr} ({format_type(base_attr_type)}):")
                            click.echo("\n".join([f'{" " * 12}' + desc for desc in attr_type.__metadata__]))
                            if default_help_str:
                                click.echo(f'{" " * 12}' + default_help_str)
                        if base_attr_type in [str, int, float, bool, Optional[int], Optional[float], Optional[str]]:
                            if attr not in [p.name for p in ctx.command.params]:
                                is_flag = base_attr_type in [bool, Optional[bool]] and not default
                                ctx.command.params.append(
                                    click.Option([f"--{attr}"], help=" ".join(attr_type.__metadata__ + (default_help_str,)), type=base_attr_type, default=default, is_flag=is_flag)
                                )
        if display_help:
            ctx.exit()

        super().parse_args(ctx, args)
