import tempfile

import datasets

from marker.v2.providers.pdf import PdfProvider
from marker.v2.schema.config.pdf import PdfProviderConfig


def test_pdf_provider():
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index('adversarial.pdf')

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    provider = PdfProvider(temp_pdf.name, PdfProviderConfig())
    assert len(provider) == 12
    assert provider.get_image(0, 72).size == (612, 792)
    assert provider.get_image(0, 96).size == (816, 1056)
    lines, spans_list = provider.get_page_lines(0)
    assert len(spans_list) == 93
    spans = spans_list[0]
    assert len(spans) == 1
    assert spans[0].text == "Subspace Adversarial Training"
    assert spans[0].font == "NimbusRomNo9L-Medi"
    assert spans[0].formats == ["plain"]

    # for line in provider.get_page_lines(0):
    #     for span in line.spans:
    #         print(f"{span=}")


if __name__ == "__main__":
    test_pdf_provider()
