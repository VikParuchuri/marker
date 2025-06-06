import click

from benchmarks.overall.download.llamaparse import LlamaParseDownloader
from benchmarks.overall.download.mathpix import MathpixDownloader
from benchmarks.overall.download.mistral import MistralDownloader


@click.command("Download data from inference services")
@click.argument("service", type=click.Choice(["mathpix", "llamaparse", "mistral"]))
@click.option("--max_rows", type=int, default=2200)
@click.option("--api_key", type=str, default=None)
@click.option("--app_id", type=str, default=None)
def main(service: str, max_rows: int, api_key: str, app_id: str):
    registry = {
        "mathpix": MathpixDownloader,
        "llamaparse": LlamaParseDownloader,
        "mistral": MistralDownloader,
    }
    downloader = registry[service](api_key, app_id, max_rows=max_rows)

    # Generate data and upload to hub
    downloader()

if __name__ == "__main__":
    main()
