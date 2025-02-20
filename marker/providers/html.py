import os
import tempfile

from weasyprint import HTML

from marker.providers.pdf import PdfProvider

class HTMLProvider(PdfProvider):
    def __init__(self, filepath: str, config=None):
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=f".pdf")
        self.temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        # Convert HTML to PDF
        try:
            self.convert_html_to_pdf(filepath)
        except Exception as e:
            raise RuntimeError(f"Failed to convert {filepath} to PDF: {e}")

        # Initialize the PDF provider with the temp pdf path
        super().__init__(self.temp_pdf_path, config)

    def __del__(self):
        if os.path.exists(self.temp_pdf_path):
            os.remove(self.temp_pdf_path)

    def convert_html_to_pdf(self, filepath: str):
        HTML(filename=filepath, encoding="utf-8").write_pdf(
            self.temp_pdf_path,
        )
