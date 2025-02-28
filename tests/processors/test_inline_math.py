from unittest.mock import Mock

import pytest

from marker.processors.llm.llm_meta import LLMSimpleBlockMetaProcessor
from marker.processors.llm.llm_inlinemath import LLMInlineMathLinesProcessor
from marker.schema import BlockTypes


@pytest.mark.filename("adversarial.pdf")
@pytest.mark.config({"page_range": [0], "use_llm": True})
def test_llm_text_processor(pdf_document, mocker):
    # Get all inline math lines
    text_lines = pdf_document.contained_blocks((BlockTypes.Line,))
    text_lines = [line for line in text_lines if line.formats and "math" in line.formats]
    assert len(text_lines) == 8
    corrected_lines = ["<math>Text</math>"] * len(text_lines)

    mock_cls = Mock()
    mock_cls.return_value = {"corrected_lines": corrected_lines}

    config = {"use_llm": True, "gemini_api_key": "test"}
    processor_lst = [LLMInlineMathLinesProcessor(config)]
    processor = LLMSimpleBlockMetaProcessor(processor_lst, mock_cls, config)
    processor(pdf_document)

    contained_spans = text_lines[0].contained_blocks(pdf_document, (BlockTypes.Span,))
    assert contained_spans[0].text == "Text\n" # Newline inserted at end of line
    assert contained_spans[0].formats == ["math"]


@pytest.mark.filename("adversarial.pdf")
@pytest.mark.config({"page_range": [0]})
def test_llm_text_processor_disabled(pdf_document):
    # Get all inline math lines
    text_lines = pdf_document.contained_blocks((BlockTypes.Line,))
    text_lines = [line for line in text_lines if line.formats and "math" in line.formats]
    assert len(text_lines) == 0


@pytest.mark.filename("adversarial.pdf")
@pytest.mark.config({"page_range": [0], "texify_inline_spans": True})
def test_llm_text_processor_texify(pdf_document):
    # Get all inline math lines
    text_lines = pdf_document.contained_blocks((BlockTypes.Line,))
    text_lines = [line for line in text_lines if line.formats and "math" in line.formats]
    assert len(text_lines) == 8