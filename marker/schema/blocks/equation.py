import html

from marker.schema import BlockTypes
from marker.schema.blocks import Block


class Equation(Block):
    block_type: BlockTypes = BlockTypes.Equation
    latex: str | None = None

    def assemble_html(self, child_blocks, parent_structure=None):
        if self.latex:
            html_out = f"<p block-type='{self.block_type}'>"
            for el in self.parse_latex(html.escape(self.latex)):
                if el["class"] == "block":
                    html_out += f'<math display="block">{el["content"]}</math>'
                elif el["class"] == "inline":
                    html_out += f'<math display="inline">{el["content"]}</math>'
                else:
                    html_out += el["content"]
            html_out += "</p>"
            return html_out
        else:
            template = super().assemble_html(child_blocks, parent_structure)
            return f"<p block-type='{self.block_type}'>{template}</p>"

    @staticmethod
    def parse_latex(text: str):
        DELIMITERS = [
            ("$$", "block"),
            ("$", "inline")
        ]
        
        text = text.replace("\n", "<br>") # we can't handle \n's inside <p> properly if we don't do this
       
        i = 0
        stack = []
        result = []
        buffer = ""

        while i < len(text):
            for delim, class_name in DELIMITERS:
                if text[i:].startswith(delim):
                    if stack and stack[-1] == delim:  # Closing
                        stack.pop()
                        result.append({"class": class_name, "content": buffer})
                        buffer = ""
                        i += len(delim)
                        break
                    elif not stack:  # Opening
                        if buffer:
                            result.append({"class": "text", "content": buffer})
                        stack.append(delim)
                        buffer = ""
                        i += len(delim)
                        break
                    else:
                        raise ValueError(f"Nested {class_name} delimiters not supported")
            else:  # No delimiter match
                buffer += text[i]
                i += 1
                
        if buffer:
            result.append({"class": "text", "content": buffer})
        return result