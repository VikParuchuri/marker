import subprocess
import tempfile
import pypdfium2 as pdfium
from typing import Dict
from collections import defaultdict
import re
import io
import json

from PIL import Image
import datasets
import markdown2
from playwright.sync_api import sync_playwright

from benchmarks.overall.schema import FullResult

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


def markdown_to_image(md: str) -> Image.Image:
    html = convert_to_html(md)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(f"""
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
                        renderMathInElement(document.body, {{
                            delimiters: [
                                {{left: '$$', right: '$$', display: true}},
                                {{left: '$', right: '$', display: false}}
                            ]
                        }});
                    </script>
            </body>
        """)
        page.set_viewport_size({"width": 1200, "height": 800})
        page.wait_for_timeout(500) # Wait for KaTeX to render
        screenshot_bytes = page.screenshot(full_page=True)
        browser.close()

    return Image.open(io.BytesIO(screenshot_bytes))


def build_dataset(ds: datasets.Dataset, all_scores: Dict[str, FullResult]) -> datasets.Dataset:
    # Get all the dataset indices that went through inference
    full_idxs = None
    for method in all_scores:
        result_idxs = list(all_scores[method]["raw_scores"].keys())
        if full_idxs is None:
            full_idxs = sorted(result_idxs)
        else:
            full_idxs = [f for f in full_idxs if f in result_idxs]

    ds_rows = defaultdict(dict)
    for idx in full_idxs:
        row = ds[idx] # img, gt_blocks, classification, language, uuid
        for method in all_scores:
            method_row = all_scores[method]["raw_scores"][idx]
            ds_rows[idx].update({
                f"{method}_score": method_row["overall_score"],
                f"{method}_markdown": method_row["markdown"],
                f"{method}_image": markdown_to_image(method_row["markdown"]),
                f"{method}_time": method_row["time"]
            })
        gt_md = "\n\n".join([clean_input(convert_to_md(block)) for block in json.loads(row["gt_blocks"])])
        ds_rows[idx].update({
            "gt_markdown": gt_md,
            "gt_image": markdown_to_image(gt_md)
        })
    out_dataset = datasets.Dataset.from_list([ds_rows[k] for k in full_idxs])
    return out_dataset

