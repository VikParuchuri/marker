from typing import Annotated

from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class LineNumbersProcessor(BaseProcessor):
    """
    A processor for ignoring line numbers.
    """
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)
    strip_numbers_threshold: Annotated[
        float,
        "The fraction of lines or tokens in a block that must be numeric to consider them as line numbers.",
    ] = 0.6
    min_lines_in_block: Annotated[
        int,
        "The minimum number of lines required in a block for it to be considered during processing.",
        "Ensures that small blocks are ignored as they are unlikely to contain meaningful line numbers.",
    ] = 4
    min_line_length: Annotated[
        int,
        "The minimum length of a line (in characters) to consider it significant when checking for",
        "numeric prefixes or suffixes. Prevents false positives for short lines.",
    ] = 10
    min_line_number_span_ratio: Annotated[
        float,
        "The minimum ratio of detected line number spans to total lines required to treat them as line numbers.",
    ] = .6

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        self.ignore_line_number_spans(document)
        self.ignore_line_starts_ends(document)
        self.ignore_line_number_blocks(document)

    def ignore_line_number_spans(self, document: Document):
        for page in document.pages:
            line_count = 0
            line_number_spans = []
            for block in page.contained_blocks(document, (BlockTypes.Line,)):
                if block.structure is None:
                    continue

                line_count += 1
                leftmost_span = None
                for span in block.contained_blocks(document, (BlockTypes.Span,)):
                    if leftmost_span is None or span.polygon.x_start < leftmost_span.polygon.x_start:
                        leftmost_span = span

                if leftmost_span is not None and leftmost_span.text.strip().isnumeric():
                    line_number_spans.append(leftmost_span)

            if line_count > 0 and len(line_number_spans) / line_count > self.min_line_number_span_ratio:
                for span in line_number_spans:
                    span.ignore_for_output = True

    def ignore_line_number_blocks(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                raw_text = block.raw_text(document)
                tokens = raw_text.strip().split()
                if len(tokens) < 4:
                    continue

                tokens_are_numbers = [token.isdigit() for token in tokens]
                if all([
                    sum(tokens_are_numbers) / len(tokens) > self.strip_numbers_threshold,
                    block.polygon.height > block.polygon.width  # Ensure block is taller than it is wide, like vertical page numbers
                ]):
                    block.ignore_for_output = True

    def ignore_line_starts_ends(self, document: Document):
        for page in document.pages:
            for block in page.contained_blocks(document, self.block_types):
                if block.structure is None:
                    continue

                all_lines = block.structure_blocks(document)
                if len(all_lines) < self.min_lines_in_block:
                    continue

                starts_with_number = []
                ends_with_number = []
                for line in all_lines:
                    spans = line.structure_blocks(document)
                    if len(spans) < 2:
                        starts_with_number.append(False)
                        ends_with_number.append(False)
                        continue

                    raw_text = line.raw_text(document)
                    starts = all([
                        spans[0].text.strip().isdigit(),
                        len(raw_text) - len(spans[0].text.strip()) > self.min_line_length
                    ])

                    ends = all([
                        spans[-1].text.strip().isdigit(),
                        len(raw_text) - len(spans[-1].text.strip()) > self.min_line_length
                    ])

                    starts_with_number.append(starts)
                    ends_with_number.append(ends)

                if sum(starts_with_number) / len(starts_with_number) > self.strip_numbers_threshold:
                    for starts, line in zip(starts_with_number, all_lines):
                        if starts:
                            span = page.get_block(line.structure[0])
                            span.ignore_for_output = True

                if sum(ends_with_number) / len(ends_with_number) > self.strip_numbers_threshold:
                    for ends, line in zip(ends_with_number, all_lines):
                        if ends:
                            span = page.get_block(line.structure[-1])
                            span.ignore_for_output = True
