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
        @bottom-center {
            content: counter(page);
        }
    }
    
    /* Force images to fit within page bounds */
    img {
        max-width: 100% !important;
        max-height: 25cm !important;  /* A4 height minus margins */
        object-fit: contain;
        margin: 1em auto;
    }
    
    /* Handle images that are inside centered paragraphs */
    .center img {
        margin-left: auto;
        margin-right: auto;
    }
    
    /* Prevent content overflow */
    div, p, table {
        max-width: 100%;
        box-sizing: border-box;
        overflow-wrap: break-word;
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
                full_data_uri = match.group(0)
                base64_str = full_data_uri.split('base64,')[1]

                img_data = base64.b64decode(base64_str)

                with BytesIO(img_data) as bio:
                    with Image.open(bio) as img:
                        output = BytesIO()
                        img.save(output, format=img.format)
                        new_base64 = base64.b64encode(output.getvalue()).decode()
                        return f'data:{match.group(1)};base64,{new_base64}'

            except Exception as e:
                print(e)
                return ""  # we ditch broken images

        return re.sub(pattern, convert_image, html_content)
