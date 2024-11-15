from markdownify import markdownify
from marker.v2.renderers.html import HTMLRenderer

class MarkdownRenderer(HTMLRenderer):
    def __call__(self, document_output):
        full_html = self.extract_html(document_output)
        return markdownify(
            full_html,
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=False
        )


