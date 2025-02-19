import re

from bs4 import BeautifulSoup

from marker.schema import BlockTypes
from marker.schema.groups import PageGroup
from marker.schema.registry import get_block_class
from marker.schema.text import Line


def add_math_spans_to_line(corrected_text: str, text_line: Line, page: PageGroup):
    SpanClass = get_block_class(BlockTypes.Span)
    corrected_spans = text_to_spans(corrected_text)

    for span_idx, span in enumerate(corrected_spans):
        if span_idx == len(corrected_spans) - 1:
            span['content'] += "\n"

        span_block = page.add_full_block(
            SpanClass(
                polygon=text_line.polygon,
                text=span['content'],
                font='Unknown',
                font_weight=0,
                font_size=0,
                minimum_position=0,
                maximum_position=0,
                formats=[span['type']],
                url=span.get('url'),
                page_id=text_line.page_id,
                text_extraction_method="gemini",
            )
        )
        text_line.structure.append(span_block.id)


def text_to_spans(text):
    soup = BeautifulSoup(text, 'html.parser')

    tag_types = {
        'b': 'bold',
        'i': 'italic',
        'math': 'math',
    }
    spans = []

    for element in soup.descendants:
        if not len(list(element.parents)) == 1:
            continue

        url = element.attrs.get('href') if hasattr(element, 'attrs') else None

        if element.name in tag_types:
            text = element.get_text()
            if element.name == "math":
                text = (text
                        .replace('\n', '\\n')
                        .replace('\t', '\\t')
                        .replace('\r', '\\r'))
            spans.append({
                'type': tag_types[element.name],
                'content': text,
                'url': url
            })
        elif element.string:
            spans.append({
                'type': 'plain',
                'content': element.string,
                'url': url
            })

    return spans