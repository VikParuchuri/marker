from typing import List
import json

from PIL import Image

from benchmarks.overall.methods import BaseMethod, BenchmarkResult


class GTMethod(BaseMethod):
    def __call__(self, sample) -> BenchmarkResult:
        gt_blocks = json.loads(sample["gt_blocks"])
        gt_html = [block["html"] for block in gt_blocks if len(block["html"]) > 0]
        gt_markdown = [self.convert_to_md(block) for block in gt_html]
        return {
            "markdown": gt_markdown,
            "time": 0
        }

    def render(self, html: List[str]) -> Image.Image:
        joined = "\n\n".join(html)
        html = f"""
<html>
<head></head>
<body>
{joined}
</body>
</html>
""".strip()
        return self.html_to_image(html)