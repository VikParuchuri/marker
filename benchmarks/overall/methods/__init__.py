import io
import random
import re
from typing import Tuple

import markdown2
from PIL import Image
from playwright.sync_api import sync_playwright

from benchmarks.overall.methods.schema import BenchmarkResult
from marker.renderers.markdown import MarkdownRenderer


class BaseMethod:
    def __init__(self, **kwargs):
        for kwarg in kwargs:
            if hasattr(self, kwarg):
                setattr(self, kwarg, kwargs[kwarg])

    @staticmethod
    def convert_to_md(html: str):
        md = MarkdownRenderer()
        markdown = md.md_cls.convert(html)
        return markdown

    def __call__(self, sample) -> BenchmarkResult:
        raise NotImplementedError()

    def render(self, markdown: str):
        return self.html_to_image(self.convert_to_html(markdown))

    @staticmethod
    def convert_to_html(md: str):
        block_placeholders = []
        inline_placeholders = []

        # Add placeholders for the math
        def block_sub(match):
            content = match.group(1)
            placeholder = f"1BLOCKMATH{len(block_placeholders)}1"
            block_placeholders.append((placeholder, f"$${content}$$"))
            return placeholder

        def inline_sub(match):
            content = match.group(1)
            placeholder = f"1INLINEMATH{len(inline_placeholders)}1"
            inline_placeholders.append((placeholder, f"${content}$"))
            return placeholder

        md = re.sub(r'\${2}(.*?)\${2}', block_sub, md, flags=re.DOTALL)
        md = re.sub(r'\$(.*?)\$', inline_sub, md)

        html = markdown2.markdown(md, extras=['tables'])

        # Replace placeholders
        for placeholder, math_str in block_placeholders:
            html = html.replace(placeholder, math_str)
        for placeholder, math_str in inline_placeholders:
            html = html.replace(placeholder, math_str)

        return html

    def html_to_image(self, html: str) -> Image.Image:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            html_str = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.css" integrity="sha384-zh0CIslj+VczCZtlzBcjt5ppRcsAmDnRem7ESsYwWwg3m/OaJ2l4x7YBZl9Kxxib" crossorigin="anonymous">
                    <!-- The loading of KaTeX is deferred to speed up page rendering -->
                    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/katex.min.js" integrity="sha384-Rma6DA2IPUwhNxmrB/7S3Tno0YY7sFu9WSYMCuulLhIqYSGZ2gKCJWIqhBWqMQfh" crossorigin="anonymous"></script>
                    <!-- To automatically render math in text elements, include the auto-render extension: -->
                    <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.21/dist/contrib/auto-render.min.js" integrity="sha384-hCXGrW6PitJEwbkoStFjeJxv+fSOOQKOPbJxSfM6G5sWZjAyWhXiTIIAmQqnlLlh" crossorigin="anonymous"></script>
                </head>
                <body>
                    {html}
                        <script>
                        document.addEventListener("DOMContentLoaded", function() {{
                            renderMathInElement(document.body, {{
                                delimiters: [
                                    {{left: '$$', right: '$$', display: true}},
                                    {{left: '$', right: '$', display: false}}
                                ],
                                throwOnError : false
                            }});
                        }});
                        </script>
                </body>
            </html>
            """.strip()
            page.set_viewport_size({"width": 1200, "height": 800})
            page.set_content(html_str)
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(500)  # Wait for KaTeX to render
            screenshot_bytes = page.screenshot(full_page=True)
            browser.close()

        return Image.open(io.BytesIO(screenshot_bytes))