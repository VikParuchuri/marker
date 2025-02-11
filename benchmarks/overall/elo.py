import json
import random
import time
from dataclasses import dataclass
from typing import List, Dict, Tuple, Literal
from PIL import Image

import click
import datasets
from google import genai
from google.genai.errors import APIError
from pydantic import BaseModel
from tqdm import tqdm

from marker.settings import settings

rating_prompt = """
You're a document analysis expert who is comparing two different markdown samples to an image to see which one represents the content of the image better. The markdown will be called version A and version B.

Here are some notes on the image and markdown:
- Some parts of the page may have been recognized as images and linked from the markdown, like `![](_page_0_Picture_0.jpeg)`.
- Tables will be formatted as Github flavored markdown.
- Block equations will be in LaTeX.
- The image and markdown may be in any language.
- The markdown is based on the text extracted from the document, and sometimes the document may have had bad OCR applied to it, resulting in gibberish text.

The markdown should fully capture the meaning and formatting of the text in the image. You'll evaluate the markdown based on the image provided.

**Instructions**
Follow this process to evaluate the markdown:
1. Carefully examine the image.
2. Carefully examine the first markdown input provided.
3. Describe how well version a represents the image.
4. Carefully examine the second markdown input provided.
5. Describe how well version B represents the image.
6. Compare version A and version B.
7. Decide which markdown representation is better, based on the criteria below.  Output version_a if version a is better, and version_b if version b is better.

Use these criteria when judging the markdown:
- Overall - the overall quality of the markdown as compared to the image.
- Text quality - the quality of the text extraction from the image.
- Formatting quality - the quality of the formatting applied to the markdown, as compared to the image.
- Tables - how effectively the tables have been extracted and formatted.
- Forms - how effectively the forms have extracted and formatted.
- Equations - how effectively block equations have been converted to LaTeX.
- Lists - if the lists have been properly extracted and formatted.
- Images - if images are identified and placed correctly.

Notes on scoring:
- Perfect markdown will include all of the important text from the image, and the formatting will be correct (minor mistakes okay).  It's okay to omit some text that isn't important to the meaning, like page numbers and chapter headings.  If the entire page is an image, it's okay if the markdown is just a link to the image, unless the image would be better represented as text.
- Bad markdown will have major missing text segments from the markdown or completely unreadable formatting.

Output json, like in the example below.

**Example**
Version A
```markdown
# *Section 1*
This is some *markdown* extracted from a document.  Here is a block equation:
$$\frac{ab \cdot x^5 + x^2 + 2 \cdot x + 123}{t}$$
```
Version B
```markdown
# Section 1
This is some markdown extracted from a document.  Here is a block equation:
$$\frac{ab \cdot x^5 + x^2 + 2 \cdot x + 123}{t}$$
```
Output
```json
{
    "image_description": "In the image, there is a section header 'Section 1', followed by some text and a block equation.",
    "version_a_description": "In the markdown, there is a section header 'Section 1', followed by some text and a block equation.",
    "version_b_description": "In the markdown, there is a section header 'Section 1', followed by some text and a block equation.  The formatting in version b is slightly different from the image.",
    "comparison": "Version A is better than version B.  The text and formatting in version A matches the image better than version B.",
    "winner": "version_a",
}
```
**Input**
Version A
```markdown
{{version_a}}
```
Version B
```markdown
{{version_b}}
```
**Output**
"""

class ComparerSchema(BaseModel):
    image_description: str
    version_a_description: str
    version_b_description: str
    comparison: str
    winner: Literal["version_a", "version_b"]


class Comparer:
    def __init__(self):
        pass

    def __call__(
        self,
        img: Image.Image,
        version_a: str,
        version_b: str
    ) -> str | None:
        hydrated_prompt = rating_prompt.replace("{{version_a}}", version_a).replace("{{version_b}}", version_b)
        try:
            rating = self.llm_rater(img, hydrated_prompt)
        except Exception as e:
            print(f"Error: {e}")
            return
        return rating


    def llm_rater(self, img: Image.Image, prompt: str):
        response = self.llm_response_wrapper(
            [img, prompt],
            ComparerSchema
        )
        assert "winner" in response, f"Response missing 'winner' key: {response}"
        return response["winner"]

    def llm_response_wrapper(
        self,
        prompt,
        response_schema,
    ):
        client = genai.Client(
            api_key=settings.GOOGLE_API_KEY,
            http_options={"timeout": 60000}
        )
        try:
            responses = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config={
                    "temperature": 0,
                    "response_schema": response_schema,
                    "response_mime_type": "application/json",
                },
            )
            output = responses.candidates[0].content.parts[0].text
            return json.loads(output)
        except APIError as e:
            print(f"Hit Gemini rate limit")
            return
        except Exception as e:
            print(f"Error: {e}")
            return

@dataclass
class Method:
    name: str
    rating: float = 1500
    k_factor: float = 32


class EloSystem:
    def __init__(self, player_names: List[str]):
        self.methods = {name: Method(name) for name in player_names}

    def expected_score(self, rating_a: float, rating_b: float) -> float:
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def update_ratings(self, winner: str, loser: str) -> Tuple[float, float]:
        method_a = self.methods[winner]
        method_b = self.methods[loser]

        expected_a = self.expected_score(method_a.rating, method_b.rating)
        expected_b = self.expected_score(method_b.rating, method_a.rating)

        # Winner gets score of 1, loser gets 0
        method_a.rating += method_a.k_factor * (1 - expected_a)
        method_b.rating += method_b.k_factor * (0 - expected_b)

        return method_a.rating, method_b.rating


@click.command("Calculate ELO scores for document conversion methods")
@click.argument("dataset", type=str)
@click.option("--methods", type=str, help="List of methods to compare: comma separated like marker,mathpix")
@click.option("--row_samples", type=int, default=2, help="Number of samples per row")
@click.option("--max_rows", type=int, default=100, help="Maximum number of rows to process")
def main(
    dataset: str,
    methods: str,
    row_samples: int,
    max_rows: int
):
    ds = datasets.load_dataset(dataset, split="train")
    method_lst = methods.split(",")
    elo = EloSystem(method_lst)
    comparer = Comparer()

    for i in tqdm(range(min(len(ds), max_rows)), desc="Calculating ELO"):
        row = ds[i]
        # Avoid any bias in ordering
        random.shuffle(method_lst)

        for j, method_a in enumerate(method_lst[:-1]):
            for z, method_b in enumerate(method_lst[j:]):
                if method_a == method_b:
                    continue

                method_a_md = row[f"{method_a}_md"]
                method_b_md = row[f"{method_b}_md"]
                winner = comparer(row["img"], method_a_md, method_b_md)
                if not winner:
                    continue

                if winner == "version_a":
                    elo.update_ratings(method_a, method_b)
                else:
                    elo.update_ratings(method_b, method_a)
        if i % 10 == 0:
            print(elo.methods)

    # Print out ratings
    print(elo.methods)


if __name__ == "__main__":
    main()