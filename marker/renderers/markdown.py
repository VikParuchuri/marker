import re
from typing import List

import regex
from markdownify import MarkdownConverter
from pydantic import BaseModel

from marker.renderers.html import HTMLRenderer
from marker.schema import BlockTypes
from marker.schema.document import Document


def cleanup_text(full_text):
    full_text = re.sub(r'\n{3,}', '\n\n', full_text)
    full_text = re.sub(r'(\n\s){3,}', '\n\n', full_text)
    return full_text


class Markdownify(MarkdownConverter):
    def __init__(self, paginate_output, page_separator, inline_math_delimiters, block_math_delimiters, **kwargs):
        super().__init__(**kwargs)
        self.paginate_output = paginate_output
        self.page_separator = page_separator
        self.inline_math_delimiters = inline_math_delimiters
        self.block_math_delimiters = block_math_delimiters

    def convert_div(self, el, text, convert_as_inline):
        is_page = el.has_attr('class') and el['class'][0] == 'page'
        if self.paginate_output and is_page:
            page_id = el['data-page-id']
            pagination_item = "\n\n" + "{" + str(page_id) + "}" + self.page_separator + "\n\n"
            return pagination_item + text
        else:
            return text

    def convert_p(self, el, text, convert_as_inline):
        hyphens = r'-—¬'
        has_continuation = el.has_attr('class') and 'has-continuation' in el['class']
        if has_continuation:
            block_type = BlockTypes[el['block-type']]
            if block_type in [BlockTypes.TextInlineMath, BlockTypes.Text]:
                if regex.compile(rf'.*[\p{{Ll}}|\d][{hyphens}]\s?$', regex.DOTALL).match(text):  # handle hypenation across pages
                    return regex.split(rf"[{hyphens}]\s?$", text)[0]
                return f"{text} "
            if block_type == BlockTypes.ListGroup:
                return f"{text}"
        return f"{text}\n\n" if text else ""  # default convert_p behavior

    def convert_math(self, el, text, convert_as_inline):
        inline = el.has_attr('display') and el['display'] == 'inline'
        if inline:
            return self.inline_math_delimiters[0] + text + self.inline_math_delimiters[1]
        else:
            return "\n" + self.block_math_delimiters[0] + text + self.block_math_delimiters[1] + "\n"

    def convert_td(self, el, text, convert_as_inline):
        text = text.replace("|", " ").replace("\n", " ")
        return super().convert_td(el, text, convert_as_inline)

    def convert_th(self, el, text, convert_as_inline):
        text = text.replace("|", " ").replace("\n", " ")
        return super().convert_th(el, text, convert_as_inline)



class MarkdownOutput(BaseModel):
    markdown: str
    images: dict
    metadata: dict


class MarkdownRenderer(HTMLRenderer):
    page_separator: str = "-" * 48
    inline_math_delimiters: List[str] = ["$", "$"]
    block_math_delimiters: List[str] = ["$$", "$$"]

    def __call__(self, document: Document) -> MarkdownOutput:
        document_output = document.render()
        full_html, images = self.extract_html(document, document_output)
        md_cls = Markdownify(
            self.paginate_output,
            self.page_separator,
            heading_style="ATX",
            bullets="-",
            escape_misc=False,
            escape_underscores=False,
            escape_asterisks=False,
            sub_symbol="<sub>",
            sup_symbol="<sup>",
            inline_math_delimiters=self.inline_math_delimiters,
            block_math_delimiters=self.block_math_delimiters
        )
        markdown = md_cls.convert(full_html)
        markdown = cleanup_text(markdown)
        return MarkdownOutput(
            markdown=markdown,
            images=images,
            metadata=self.generate_document_metadata(document, document_output)
        )
