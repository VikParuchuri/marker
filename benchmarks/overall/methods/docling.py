import tempfile
import time

from benchmarks.overall.methods import BaseMethod, BenchmarkResult


class DoclingMethod(BaseMethod):
    model_dict: dict = None
    use_llm: bool = False

    def __call__(self, sample) -> BenchmarkResult:
        from docling.document_converter import DocumentConverter
        pdf_bytes = sample["pdf"]  # This is a single page PDF
        converter = DocumentConverter()

        with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
            f.write(pdf_bytes)
            start = time.time()
            result = converter.convert(f.name)
            total = time.time() - start

        return {
            "markdown": result.document.export_to_markdown(),
            "time": total
        }

