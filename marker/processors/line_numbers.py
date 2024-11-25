from marker.processors import BaseProcessor
from marker.schema import BlockTypes
from marker.schema.document import Document


class LineNumbersProcessor(BaseProcessor):
    block_types = (BlockTypes.Text, BlockTypes.TextInlineMath)
    strip_numbers_threshold: int = .6
    min_lines_in_block: int = 4
    min_line_length: int = 10

    def __init__(self, config):
        super().__init__(config)

    def __call__(self, document: Document):
        self.ignore_line_starts_ends(document)
        self.ignore_line_number_blocks(document)

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
                    block.polygon.height > block.polygon.width # Ensure block is taller than it is wide, like vertical page numbers
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

                    ends= all([
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

