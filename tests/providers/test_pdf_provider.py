import pytest


@pytest.mark.config({"page_range": [0]})
def test_pdf_provider(pdf_provider):
    assert len(pdf_provider) == 12
    assert pdf_provider.get_image(0, 72).size == (612, 792)
    assert pdf_provider.get_image(0, 96).size == (816, 1056)

    page_lines = pdf_provider.get_page_spans(0)
    spans_list = [span for line in page_lines for span in line.spans]
    assert len(spans_list) == 93

    spans = spans_list[0]
    assert len(spans) == 2
    assert spans[0].text == "Subspace Adversarial Training"
    assert spans[0].font == "NimbusRomNo9L-Medi"
    assert spans[0].formats == ["plain"]
