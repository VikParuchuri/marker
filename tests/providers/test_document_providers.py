import pytest


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("lambda.pptx")
def test_pptx_provider(doc_provider):
    assert len(doc_provider) == 22
    assert doc_provider.get_images([0], 72)[0].size == (842, 596)

    page_lines = doc_provider.get_page_lines(0)
    assert len(page_lines) == 26

    spans = page_lines[0].spans
    assert len(spans) == 2
    assert spans[0].text == "Lambda Calculus"

    spans = page_lines[1].spans
    assert spans[0].text == "CSE 340 – Principles of Programming Languages"


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("manual.epub")
def test_epub_provider(doc_provider):
    assert len(doc_provider) == 20
    assert doc_provider.get_images([0], 72)[0].size == (596, 842)

    page_lines = doc_provider.get_page_lines(0)
    assert len(page_lines) == 31

    spans = page_lines[0].spans
    assert len(spans) == 2
    assert spans[0].text == "The Project Gutenberg eBook of Simple Sabotage Field"


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("china.html")
def test_html_provider(doc_provider):
    assert len(doc_provider) == 73
    assert doc_provider.get_images([0], 72)[0].size == (596, 842)

    page_lines = doc_provider.get_page_lines(0)
    assert len(page_lines) == 55

    spans = page_lines[0].spans
    assert len(spans) == 2
    assert spans[0].text == "Jump to content"

@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("gatsby.docx")
def test_docx_provider(doc_provider):
    assert len(doc_provider) == 2
    assert doc_provider.get_images([0], 72)[0].size == (596, 842)

    page_lines = doc_provider.get_page_lines(0)
    assert len(page_lines) == 54

    spans = page_lines[0].spans
    assert len(spans) == 2
    assert spans[0].text == "Themes"


@pytest.mark.config({"page_range": [0]})
@pytest.mark.filename("single_sheet.xlsx")
def test_xlsx_provider(doc_provider):
    assert len(doc_provider) == 1
    assert doc_provider.get_images([0], 72)[0].size == (842, 596)

    page_lines = doc_provider.get_page_lines(0)
    assert len(page_lines) == 4

    spans = page_lines[0].spans
    assert len(spans) == 2
    assert spans[0].text == "Sheet1"