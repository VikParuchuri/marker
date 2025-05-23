import base64
import os
import re
import tempfile
from io import BytesIO

from PIL import Image
from marker.logger import get_logger

from marker.providers.pdf import PdfProvider

logger = get_logger()

css = """
@page {
    size: A4;
    margin: 2cm;
}

img {
    max-width: 100%;
    max-height: 25cm;
    object-fit: contain;
    margin: 12pt auto;
}

div, p {
    max-width: 100%;
    word-break: break-word;
    font-size: 10pt;
}

table {
    width: 100%;
    border-collapse: collapse;
    break-inside: auto;
    font-size: 10pt;
}

tr {
    break-inside: avoid;
    page-break-inside: avoid;
}

td {
    border: 0.75pt solid #000;
    padding: 6pt;
}
"""


class DocumentProvider(PdfProvider):
    def __init__(self, filepath: str, config=None):
        temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        self.temp_pdf_path = temp_pdf.name
        temp_pdf.close()

        # Convert DOCX to PDF
        try:
            self.convert_docx_to_pdf(filepath)
        except Exception as e:
            raise RuntimeError(f"Failed to convert {filepath} to PDF: {e}")

        # Initialize the PDF provider with the temp pdf path
        super().__init__(self.temp_pdf_path, config)

    def __del__(self):
        if os.path.exists(self.temp_pdf_path):
            os.remove(self.temp_pdf_path)

    def convert_docx_to_pdf(self, filepath: str):
        from weasyprint import CSS, HTML
        import mammoth

        with open(filepath, "rb") as docx_file:
            # we convert the docx to HTML
            result = mammoth.convert_to_html(docx_file)
            html = result.value

            # We convert the HTML into a PDF
            HTML(string=self._preprocess_base64_images(html)).write_pdf(
                self.temp_pdf_path, stylesheets=[CSS(string=css), self.get_font_css()]
            )

    @staticmethod
    def _preprocess_base64_images(html_content):
        pattern = r'data:([^;]+);base64,([^"\'>\s]+)'

        def convert_image(match):
            try:
                img_data = base64.b64decode(match.group(2))

                with BytesIO(img_data) as bio:
                    with Image.open(bio) as img:
                        output = BytesIO()
                        img.save(output, format=img.format)
                        new_base64 = base64.b64encode(output.getvalue()).decode()
                        return f"data:{match.group(1)};base64,{new_base64}"

            except Exception as e:
                logger.error(f"Failed to process image: {e}")
                return ""  # we ditch broken images as that breaks the PDF creation down the line

        return re.sub(pattern, convert_image, html_content)
