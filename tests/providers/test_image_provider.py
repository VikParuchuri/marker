from marker.providers.image import ImageProvider
from marker.renderers.markdown import MarkdownOutput


def test_image_provider(config, temp_image):
    provider = ImageProvider(temp_image.name, config)
    assert len(provider) == 1
    assert provider.get_images([0], 72)[0].size == (512, 512)

    page_lines = provider.get_page_lines(0)
    assert len(page_lines) == 0

def test_image_provider_conversion(pdf_converter, temp_image):
    markdown_output: MarkdownOutput = pdf_converter(temp_image.name)
    assert "Hello, World!" in markdown_output.markdown


