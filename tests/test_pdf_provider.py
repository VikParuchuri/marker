from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.config.pdf import PdfProviderConfig


def test_pdf_provider():
    provider = PdfProvider("/home/ubuntu/surya-test/pdfs/adversarial.pdf", PdfProviderConfig())
    assert len(provider) == 12
    assert provider.get_image(0, 72).size == (612, 792)
    assert provider.get_image(0, 96).size == (816, 1056)
    line = provider.get_page_lines(0)[0]
    spans = line.spans
    assert len(spans) == 1
    assert spans[0].text == "Subspace Adversarial Training"
    assert spans[0].font == "NimbusRomNo9L-Medi"
    assert spans[0].formats == ["plain"]

    # for line in provider.get_page_lines(0):
    #     for span in line.spans:
    #         print(f"{span=}")


if __name__ == "__main__":
    test_pdf_provider()
