import pytest

from marker.processors.document_toc import DocumentTOCProcessor


@pytest.mark.config({"page_range": [0]})
def test_document_toc_processor(pdf_document, detection_model, recognition_model, table_rec_model):
    processor = DocumentTOCProcessor()
    processor(pdf_document)

    assert len(pdf_document.table_of_contents) == 3
    assert pdf_document.table_of_contents[0]["title"] == "Subspace Adversarial Training"
