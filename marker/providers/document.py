import base64
import logging
import os
import re
from io import BytesIO

import mammoth
from PIL import Image
from weasyprint import CSS, HTML

from marker.providers.pdf import PdfProvider

logging.getLogger('fontTools.subset').setLevel(logging.ERROR)
logging.getLogger('fontTools.ttLib.ttFont').setLevel(logging.ERROR)

css = '''
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
'''


class DocumentProvider(PdfProvider):
    def __init__(self, filepath: str, config=None):
        home_dir = os.path.expanduser("~")
        rel_path = os.path.relpath(filepath, home_dir)
        base_name, _ = os.path.splitext(rel_path)
        self.temp_pdf_path = os.path.join('/tmp', f"{base_name}.pdf")

        # Convert DOCX to PDF
        try:
            self.convert_docx_to_pdf(filepath)
        except Exception as e:
            raise RuntimeError(f"Failed to convert {filepath} to PDF: {e}")

        # Initialize the PDF provider with the temp pdf path
        super().__init__(self.temp_pdf_path, config)

    def __del__(self):
        if os.path.exists(self.temp_pdf_path):
            print(f"Deleting temporary PDF file: {self.temp_pdf_path}")
            os.remove(self.temp_pdf_path)

    def convert_docx_to_pdf(self, filepath: str):
        with open(filepath, "rb") as docx_file:
            # we convert the docx to HTML
            result = mammoth.convert_to_html(docx_file)
            html = result.value

            # We convert the HTML into a PDF
            HTML(string=self._preprocess_base64_images(html)).write_pdf(
                self.temp_pdf_path,
                stylesheets=[CSS(string=css)]
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
                        return f'data:{match.group(1)};base64,{new_base64}'

            except Exception as e:
                print(e)
                return ""  # we ditch broken images as that breaks the PDF creation down the line

        return re.sub(pattern, convert_image, html_content)
