from marker.providers.pdf import PdfProvider
import tempfile

import datasets


def setup_pdf_provider(
    filename='adversarial.pdf',
    config=None,
) -> PdfProvider:
    dataset = datasets.load_dataset("datalab-to/pdfs", split="train")
    idx = dataset['filename'].index(filename)

    temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf")
    temp_pdf.write(dataset['pdf'][idx])
    temp_pdf.flush()

    provider = PdfProvider(temp_pdf.name, config)
    return provider
