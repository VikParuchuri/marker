import os
import subprocess

from marker.providers.pdf import PdfProvider


class LibreOfficeProvider(PdfProvider):
    def __init__(self, filepath: str, config=None):
        home_dir = os.path.expanduser("~")
        rel_path = os.path.relpath(filepath, home_dir)
        base_name, _ = os.path.splitext(rel_path)
        self.temp_pdf_path = os.path.join('/tmp', f"{base_name}.pdf")

        # Check if LibreOffice is installed
        try:
            version = subprocess.check_output("soffice --version", shell=True, text=True).strip()
            print(f"LibreOffice is installed: {version}")
        except subprocess.CalledProcessError:
            raise EnvironmentError("LibreOffice is not installed or not in PATH")

        # Convert DOCX to PDF
        try:
            conversion_command = f"soffice --headless --convert-to pdf --outdir {os.path.dirname(self.temp_pdf_path)} {filepath}"
            subprocess.check_output(conversion_command, shell=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to convert {filepath} to PDF: {e}")

        # Initialize the PDF provider with the temp pdf path
        super().__init__(self.temp_pdf_path, config)

    def __del__(self):
        if os.path.exists(self.temp_pdf_path):
            print(f"Deleting temporary PDF file: {self.temp_pdf_path}")
            os.remove(self.temp_pdf_path)
