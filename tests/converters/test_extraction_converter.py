import json
import pytest

from marker.converters.extraction import ExtractionConverter
from marker.extractors.page import PageExtractionSchema
from marker.services import BaseService


class MockLLMService(BaseService):
    def __call__(self, prompt, image=None, page=None, response_schema=None, **kwargs):
        assert response_schema == PageExtractionSchema
        return {
            "description": "Mock extraction description",
            "extracted_json": json.dumps({"test_key": "test_value"}),
            "existence_confidence": 5,
            "value_confidence": 5,
        }


@pytest.fixture
def mock_llm_service():
    return MockLLMService


@pytest.fixture
def extraction_converter(config, model_dict, mock_llm_service):
    test_schema = {
        "title": "TestSchema",
        "type": "object",
        "properties": {"test_key": {"title": "Test Key", "type": "string"}},
        "required": ["test_key"],
    }

    config["page_schema"] = json.dumps(test_schema)
    config["output_format"] = "markdown"
    model_dict["llm_service"] = mock_llm_service

    converter = ExtractionConverter(
        artifact_dict=model_dict, processor_list=None, config=config
    )
    converter.default_llm_service = MockLLMService
    return converter


@pytest.mark.config({"page_range": [0]})
def test_extraction_converter_invalid_schema(
    config, model_dict, mock_llm_service, temp_doc
):
    config["page_schema"] = "invalid json"

    model_dict["llm_service"] = mock_llm_service
    converter = ExtractionConverter(
        artifact_dict=model_dict, processor_list=None, config=config
    )

    with pytest.raises(ValueError):
        converter(temp_doc.name)


@pytest.mark.config({"page_range": [0, 1]})
def test_extraction_converter_multiple_pages(extraction_converter, temp_doc):
    result = extraction_converter(temp_doc.name)

    assert result is not None
    assert result.document_json is not None
    assert result.document_json == {"test_key": "test_value"}
