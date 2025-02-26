import pytest


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("lambda.pptx")
def test_pptx_provider(doc_provider):
    assert doc_provider.get_images([0], 72)[0].size == (842, 596)

    page_lines = doc_provider.get_page_lines(0)

    spans = page_lines[0].spans
    assert spans[0].text == "Lambda Calculus"

    spans = page_lines[1].spans
    assert spans[0].text == "CSE 340 – Principles of Programming Languages"


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("manual.epub")
def test_epub_provider(doc_provider):
    assert doc_provider.get_images([0], 72)[0].size == (596, 842)

    page_lines = doc_provider.get_page_lines(0)

    spans = page_lines[0].spans
    assert spans[0].text == "The Project Gutenberg eBook of Simple"


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("china.html")
def test_html_provider(doc_provider):
    assert doc_provider.get_images([0], 72)[0].size == (596, 842)

    page_lines = doc_provider.get_page_lines(0)

    spans = page_lines[0].spans
    assert spans[0].text == "Jump to content"

@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("gatsby.docx")
def test_docx_provider(doc_provider):
    assert doc_provider.get_images([0], 72)[0].size == (596, 842)

    page_lines = doc_provider.get_page_lines(0)

    spans = page_lines[0].spans
    assert spans[0].text == "Themes"


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("single_sheet.xlsx")
def test_xlsx_provider(doc_provider):
    assert doc_provider.get_images([0], 72)[0].size == (842, 596)

    page_lines = doc_provider.get_page_lines(0)

    spans = page_lines[0].spans
    assert spans[0].text == "Sheet1"