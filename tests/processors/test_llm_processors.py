from unittest.mock import MagicMock, Mock

import pytest

from marker.processors.llm.llm_form import LLMFormProcessor
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.llm.llm_text import LLMTextProcessor
from marker.processors.table import TableProcessor
from marker.schema import BlockTypes

@pytest.mark.filename("form_1040.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_form_processor_no_config(pdf_document):
    processor = LLMFormProcessor()
    processor(pdf_document)

    forms = pdf_document.contained_blocks((BlockTypes.Form,))
    assert forms[0].html is None


@pytest.mark.filename("form_1040.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_form_processor_no_cells(pdf_document):
    processor = LLMFormProcessor({"use_llm": True})
    processor(pdf_document)

    forms = pdf_document.contained_blocks((BlockTypes.Form,))
    assert forms[0].html is None


@pytest.mark.filename("form_1040.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_form_processor(pdf_document, detection_model, table_rec_model, recognition_model, mocker):
    corrected_markdown = "*This is corrected markdown.*\n" * 100

    corrected_html = "<em>This is corrected markdown.</em>\n" * 100
    corrected_html = "<p>" + corrected_html.strip() + "</p>\n"

    mock_cls = Mock()
    mock_cls.return_value.generate_response.return_value = {"corrected_markdown": corrected_markdown}
    mocker.patch("marker.processors.llm.GoogleModel", mock_cls)

    cell_processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    cell_processor(pdf_document)

    processor = LLMFormProcessor({"use_llm": True})
    processor(pdf_document)

    forms = pdf_document.contained_blocks((BlockTypes.Form,))
    assert forms[0].html == corrected_html



@pytest.mark.filename("table_ex2.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_table_processor(pdf_document, detection_model, table_rec_model, recognition_model, mocker):
    corrected_markdown = """
| Column 1 | Column 2 | Column 3 | Column 4 |
|----------|----------|----------|----------|
| Value 1  | Value 2  | Value 3  | Value 4  |
| Value 5  | Value 6  | Value 7  | Value 8  |
| Value 9  | Value 10 | Value 11 | Value 12 |
    """.strip()

    mock_cls = Mock()
    mock_cls.return_value.generate_response.return_value = {"corrected_markdown": corrected_markdown}
    mocker.patch("marker.processors.llm.GoogleModel", mock_cls)

    cell_processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    cell_processor(pdf_document)

    processor = LLMTableProcessor({"use_llm": True})
    processor(pdf_document)

    tables = pdf_document.contained_blocks((BlockTypes.Table,))
    assert tables[0].cells[0].text == "Column 1"


@pytest.mark.filename("adversarial.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_text_processor(pdf_document, mocker):
    inline_math_block = pdf_document.contained_blocks((BlockTypes.TextInlineMath,))[0]
    text_lines = inline_math_block.contained_blocks(pdf_document, (BlockTypes.Line,))
    corrected_lines = ["<i>Text</i>"] * len(text_lines)

    mock_cls = Mock()
    mock_cls.return_value.generate_response.return_value = {"corrected_lines": corrected_lines}
    mocker.patch("marker.processors.llm.GoogleModel", mock_cls)

    processor = LLMTextProcessor({"use_llm": True})
    processor(pdf_document)

    contained_spans = text_lines[0].contained_blocks(pdf_document, (BlockTypes.Span,))
    assert contained_spans[0].text == "Text\n" # Newline inserted at end of line
    assert contained_spans[0].formats == ["italic"]
