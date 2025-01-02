import importlib
import inspect
import pkgutil
from typing import Optional

import click

from marker.builders import BaseBuilder
from marker.converters import BaseConverter
from marker.processors import BaseProcessor
from marker.renderers import BaseRenderer


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

        base_classes = [BaseBuilder, BaseProcessor, BaseConverter, BaseRenderer]
        for base in base_classes:
            if display_help:
                click.echo(f"{base.__name__.removeprefix('Base')}s:\n")

            subclasses = find_subclasses(base)
            for class_name, class_type in subclasses.items():
                doc = class_type.__doc__ or ""
                if display_help and doc and "Attributes:" in doc:
                    click.echo(f"  {class_name}: {doc}")
                parsed_doc = self._parse_indentation_based_tree(doc)
                for attr, attr_type in class_type.__annotations__.items():
                    if attr in doc and attr_type in [str, int, float, bool, Optional[int], Optional[float], Optional[str]]:
                        if attr not in [p.name for p in ctx.command.params]:
                            default = getattr(class_type, attr)
                            is_flag = attr_type in [bool, Optional[bool]] and not default
                            ctx.command.params.append(
                                click.Option([f"--{attr}"], help=" ".join(parsed_doc[attr]), type=attr_type, default=default, is_flag=is_flag)
                            )
        if display_help:
            ctx.exit()

        super().parse_args(ctx, args)


    def _parse_indentation_based_tree(self, doc):
        stack = []
        tree = []

        for line in doc.splitlines():
            stripped_line = line.lstrip()
            if not stripped_line:
                continue

            indent_level = len(line) - len(stripped_line)

            node = {"content": stripped_line, "children": []}
            while stack and stack[-1]['indent'] >= indent_level:
                stack.pop()

            if stack:
                stack[-1]["children"].append(node)
            else:
                tree.append(node)

            node['indent'] = indent_level
            stack.append(node)

        attributes = {}
        for node in tree:
            if node['content'].startswith("Attributes:"):
                for child in node["children"]:
                    var = child["content"].split(" ")[0]
                    descs = [c["content"] for c in child["children"] if c]
                    attributes[var] = descs

        return attributes
