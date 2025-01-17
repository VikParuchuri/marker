from unittest.mock import Mock

import pytest

from marker.processors.llm.llm_table_merge import LLMTableMergeProcessor
from marker.processors.table import TableProcessor
from marker.schema import BlockTypes


@pytest.mark.filename("table_ex2.pdf")
def test_llm_table_processor_nomerge(pdf_document, detection_model, table_rec_model, recognition_model, mocker):
    mock_cls = Mock()
    mock_cls.return_value.generate_response.return_value = {
        "merge": "true",
        "direction": "right"
    }
    mocker.patch("marker.processors.llm.GoogleModel", mock_cls)

    cell_processor = TableProcessor(detection_model, recognition_model, table_rec_model)
    cell_processor(pdf_document)

    tables = pdf_document.contained_blocks((BlockTypes.Table,))
    assert len(tables) == 3

    processor = LLMTableMergeProcessor({"use_llm": True, "google_api_key": "test"})
    processor(pdf_document)

    tables = pdf_document.contained_blocks((BlockTypes.Table,))
    assert len(tables) == 3