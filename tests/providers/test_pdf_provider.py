import pytest


@pytest.mark.config({"page_range": [0]})
def test_pdf_provider(pdf_provider):
    assert len(pdf_provider) == 12
    assert pdf_provider.get_images([0], 72)[0].size == (612, 792)
    assert pdf_provider.get_images([0], 96)[0].size == (816, 1056)

    page_lines = pdf_provider.get_page_lines(0)
    assert len(page_lines) == 87

    spans = page_lines[0].spans
    assert len(spans) == 2
    assert spans[0].text == "Subspace Adversarial Training"
    assert spans[0].font == "NimbusRomNo9L-Medi"
    assert spans[0].formats == ["plain"]
