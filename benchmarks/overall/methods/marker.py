import tempfile
import time

from benchmarks.overall.methods import BaseMethod, BenchmarkResult
from marker.converters.pdf import PdfConverter


class MarkerMethod(BaseMethod):
    model_dict: dict = None
    use_llm: bool = False

    def __call__(self, sample) -> BenchmarkResult:
        pdf_bytes = sample["pdf"]  # This is a single page PDF
        block_converter = PdfConverter(
            artifact_dict=self.model_dict,
            config={"page_range": [0], "disable_tqdm": True, "use_llm": self.use_llm}
        )

        with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as f:
            f.write(pdf_bytes)
            start = time.time()
            rendered = block_converter(f.name)
            total = time.time() - start

        return {
            "markdown": rendered.markdown,
            "time": total
        }

