from markdownify import markdownify
from marker.v2.renderers.html import HTMLRenderer


class MarkdownRenderer(HTMLRenderer):
    def __call__(self, document):
        document_output = document.render()
        full_html = self.extract_html(document, document_output)
        return markdownify(
            full_html,
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=False
        )


