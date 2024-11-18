from markdownify import markdownify, MarkdownConverter
from pydantic import BaseModel

from marker.v2.renderers.html import HTMLRenderer


class Markdownify(MarkdownConverter):
    pass


class MarkdownOutput(BaseModel):
    markdown: str
    images: dict


class MarkdownRenderer(HTMLRenderer):
    def __call__(self, document) -> MarkdownOutput:
        document_output = document.render()
        full_html, images = self.extract_html(document, document_output)
        md_cls = Markdownify(
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=False
        )
        markdown = md_cls.convert(full_html)
        return MarkdownOutput(
            markdown=markdown,
            images=images
        )


