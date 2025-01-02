from unittest.mock import MagicMock, Mock

import pytest

from marker.processors.llm.llm_form import LLMFormProcessor
from marker.processors.llm.llm_image_description import LLMImageDescriptionProcessor
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.llm.llm_text import LLMTextProcessor
from marker.processors.table import TableProcessor
from marker.renderers.markdown import MarkdownRenderer
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
    processor = LLMFormProcessor({"use_llm": True, "google_api_key": "test"})
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

    processor = LLMFormProcessor({"use_llm": True, "google_api_key": "test"})
    processor(pdf_document)

    forms = pdf_document.contained_blocks((BlockTypes.Form,))
    assert forms[0].html == corrected_html



@pytest.mark.filename("table_ex2.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_table_processor(pdf_document, detection_model, table_rec_model, recognition_model, mocker):
    corrected_html = """
<table>
    <tr>
        <td>Column 1</td>
        <td>Column 2</td>
        <td>Column 3</td>
        <td>Column 4</td>
    </tr>
    <tr>
        <td>Value 1</td>
        <td>Value 2</td>
        <td>Value 3</td>
        <td>Value 4</td>
    </tr>
    <tr>
        <td>Value 5</td>
        <td>Value 6</td>
        <td>Value 7</td>
        <td>Value 8</td>
    </tr>
</table>
    """.strip()

    mock_cls = Mock()
    mock_cls.return_value.generate_response.return_value = {"corrected_html": corrected_html}
    mocker.patch("marker.processors.llm.GoogleModel", mock_cls)

    cell_processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    cell_processor(pdf_document)

    processor = LLMTableProcessor({"use_llm": True, "google_api_key": "test"})
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

    processor = LLMTextProcessor({"use_llm": True, "google_api_key": "test"})
    processor(pdf_document)

    contained_spans = text_lines[0].contained_blocks(pdf_document, (BlockTypes.Span,))
    assert contained_spans[0].text == "Text\n" # Newline inserted at end of line
    assert contained_spans[0].formats == ["italic"]


@pytest.mark.filename("A17_FlightPlan.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_caption_processor_disabled(pdf_document):
    processor = LLMImageDescriptionProcessor({"use_llm": True, "google_api_key": "test"})
    processor(pdf_document)

    contained_pictures = pdf_document.contained_blocks((BlockTypes.Picture, BlockTypes.Figure))
    assert all(picture.description is None for picture in contained_pictures)

@pytest.mark.filename("A17_FlightPlan.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_caption_processor(pdf_document, mocker):
    description = "This is an image description."
    mock_cls = Mock()
    mock_cls.return_value.generate_response.return_value = {"image_description": description}
    mocker.patch("marker.processors.llm.GoogleModel", mock_cls)
    processor = LLMImageDescriptionProcessor({"use_llm": True, "google_api_key": "test", "extract_images": False})
    processor(pdf_document)

    contained_pictures = pdf_document.contained_blocks((BlockTypes.Picture, BlockTypes.Figure))
    assert all(picture.description == description for picture in contained_pictures)

    # Ensure the rendering includes the description
    renderer = MarkdownRenderer({"extract_images": False})
    md = renderer(pdf_document).markdown

    assert description in md