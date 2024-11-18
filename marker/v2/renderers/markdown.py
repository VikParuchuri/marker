from markdownify import markdownify, MarkdownConverter
from pydantic import BaseModel

from marker.v2.renderers.html import HTMLRenderer
from marker.v2.schema.document import Document


class Markdownify(MarkdownConverter):
    def __init__(self, paginate_output, page_separator, **kwargs):
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator

    def convert_div(self, el, text, convert_as_inline):
        is_page = el.has_attr('class') and el['class'][0] == 'page'
        if self.paginate_output and is_page:
            page_id = el['data-page-id']
            pagination_item = "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            return pagination_item + text
        else:
            return text


class MarkdownOutput(BaseModel):
    markdown: str
    images: dict


class MarkdownRenderer(HTMLRenderer):
    page_separator: str = "-" * 48

    def __call__(self, document: Document) -> MarkdownOutput:
        document_output = document.render()
        full_html, images = self.extract_html(document, document_output)
        md_cls = Markdownify(
            self.paginate_output,
            self.page_separator,
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
