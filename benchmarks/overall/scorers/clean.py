import re
import subprocess
import tempfile
from pathlib import Path

import latex2mathml.converter

class MarkdownCleaner:
    def __init__(self):
        pass

    def __call__(self, markdown):
        markdown = self.normalize_markdown(markdown)  # Use pandoc to normalize

        # Replace math expressions with latexml
        pattern = r'(?<!\\)\$(?:\$([^$]+)\$\$|\s*([^$\n]+?)\s*\$)'
        markdown = re.sub(pattern, self.standardize_math, markdown)

        # Replace image urls with a generic tag
        pattern = r'!\[(.*?)\]\((https?://[^\s\)]+)\)'
        markdown = re.sub(pattern, r'![link]', markdown)

        # Clean up stray html tags
        markdown = markdown.replace("<br>", "\n")
        markdown = re.sub(r"<sub>(.*?)</sub>", r"\1", markdown)
        markdown = re.sub(r"<sup>(.*?)</sup>", r"\1", markdown)
        markdown = re.sub(r"<span.*?>(.*?)</span>", r"\1", markdown)  # Remove span tags and keep content

        # Clean up markdown formatting
        markdown = re.sub(r"\s+", " ", markdown)
        markdown = re.sub(r"\n+", "\n", markdown)
        markdown = re.sub("\\.+", ".",
                          markdown)  # Replace repeated periods with a single period, like in table of contents
        markdown = re.sub("#+", "#", markdown)  # Replace repeated headers with a single header
        markdown = markdown.encode().decode('unicode-escape', errors="ignore")  # Decode unicode characters properly
        return markdown.strip().lower()

    @staticmethod
    def normalize_markdown(md_text: str) -> str:
        with tempfile.TemporaryDirectory() as tmp_dir:
            dirpath = Path(tmp_dir)
            input_file = dirpath / 'input.md'
            input_file.write_text(md_text, encoding='utf-8')

            # Markdown to HTML
            html_file = dirpath / 'temp.html'
            subprocess.run(
                [
                    'pandoc',
                    str(input_file),
                    '-f', 'markdown+tex_math_dollars',
                    '-t', 'html',
                    '-o', str(html_file),
                    '--quiet'
                ],
                check=True
            )

            # HTML to Markdown
            output_file = dirpath / 'output.md'
            subprocess.run(
                [
                    'pandoc',
                    str(html_file),
                    '-f', 'html',
                    '-t', 'markdown+tex_math_dollars',
                    '-o', str(output_file),
                    '--quiet'
                ],
                check=True
            )

            # Read back the normalized Markdown
            normalized_md = output_file.read_text(encoding='utf-8')

        return normalized_md

    def standardize_math(self, match):
        try:
            delim = "$$" if match.group(0).startswith('$$') else "$"
            math_content = match.group(1) or match.group(2)
            if delim == "$$":
                math_content = latex2mathml.converter.convert(math_content)
            else:
                math_content = self.clean_latex(math_content)
            return f'{delim}{math_content}{delim}'
        except Exception as e:
            print(f"Failed to standardize math expression: {match.group(0)} with error: {e}")
            return match.group(0)

    @staticmethod
    def clean_latex(latex_str):
        latex_str = re.sub(r'\s+', ' ', latex_str.strip())
        for tag in [r'\\text', r'\\mathrm', r'\\mathbf', r'\\textbf']:
            latex_str = re.sub(tag + r'\{([^}]+)\}', r'\1', latex_str)

        replacements = {
            '\\times': '*',
            '\\cdot': '*',
            '\\div': '/',
            '\\le': '<=',
            '\\ge': '>=',
            '\\neq': '!=',
            '\\to': '\\rightarrow',
        }

        for old, new in replacements.items():
            latex_str = latex_str.replace(old, new)

        return latex_str



