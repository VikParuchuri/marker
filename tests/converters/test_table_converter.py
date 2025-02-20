import pytest
from marker.converters.table import TableConverter
from marker.renderers.markdown import MarkdownOutput
from marker.util import classes_to_strings

def _table_converter(config, model_dict, renderer, temp_pdf):
    converter = TableConverter(
        artifact_dict=model_dict,
        processor_list=None,
        renderer=classes_to_strings([renderer])[0],
        config=config
    )

    markdown_output: MarkdownOutput = converter(temp_pdf.name)
    markdown = markdown_output.markdown

    assert len(markdown) > 0
    assert "cyclic" in markdown


@pytest.mark.output_format("markdown")
@pytest.mark.config({"page_range": [5]})
def test_table_converter(config, model_dict, renderer, temp_doc):
    _table_converter(config, model_dict, renderer, temp_doc)

@pytest.mark.output_format("markdown")
@pytest.mark.config({"page_range": [5], "force_ocr": True})
def test_table_converter_ocr(config, model_dict, renderer, temp_doc):
    _table_converter(config, model_dict, renderer, temp_doc)

