from typing import Optional

import click

from marker.config.crawler import crawler


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
            click.echo("Here is a list of all the Builders, Processors, Converters, Providers and Renderers in Marker along with their attributes:")

        for base_type, base_type_dict in crawler.class_config_map.items():
            if display_help:
                click.echo(f"{base_type}s:")
            for class_name, class_map in base_type_dict.items():
                if display_help and class_map['config']:
                    click.echo(f"\n  {class_name}: {class_map['class_type'].__doc__ or ''}")
                    click.echo(" " * 4 + "Attributes:")
                for attr, (attr_type, formatted_type, default, metadata) in class_map['config'].items():
                    class_name_attr = class_name + "_" + attr

                    if display_help:
                        click.echo(" " * 8 + f"{attr} ({formatted_type}):")
                        click.echo("\n".join([f'{" " * 12}' + desc for desc in metadata]))
                    if attr_type in [str, int, float, bool, Optional[int], Optional[float], Optional[str]]:
                        is_flag = attr_type in [bool, Optional[bool]] and not default
                        if crawler.attr_counts.get(attr) > 1:
                            options = ["--" + class_name_attr]
                        else:
                            options = ["--" + attr, "--" + class_name_attr]
                        ctx.command.params.append(
                            click.Option(
                                options,
                                type=attr_type,
                                help=" ".join(metadata),
                                default=default,
                                is_flag=is_flag,
                            )
                        )

        if display_help:
            ctx.exit()

        super().parse_args(ctx, args)
