import json

from pydantic import create_model, BaseModel, Field, ValidationError
from typing import Annotated, Type, Optional, Any, Dict
from enum import Enum

from marker.extractors import BaseExtractor, ExtractionResult
from marker.schema.document import Document
from marker.schema.groups.page import PageGroup


def make_all_optional(schema: Dict[str, Any]) -> Dict[str, Any]:
    if "properties" in schema:
        for prop_schema in schema["properties"].values():
            if "required" in schema:
                schema["required"] = []

            if prop_schema.get("type") == "object":
                make_all_optional(prop_schema)

            elif prop_schema.get("type") == "array" and "items" in prop_schema:
                if prop_schema["items"].get("type") == "object":
                    make_all_optional(prop_schema["items"])

    if "definitions" in schema:
        for def_schema in schema["definitions"].values():
            make_all_optional(def_schema)

    if "$defs" in schema:
        for def_schema in schema["$defs"].values():
            make_all_optional(def_schema)

    return schema


def json_schema_to_base_model(schema: dict[str, Any]) -> Type[BaseModel]:
    type_mapping: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])
    model_fields = {}

    def process_field(field_name: str, field_props: dict[str, Any]) -> tuple:
        json_type = field_props.get("type", "string")
        enum_values = field_props.get("enum")

        if enum_values:
            enum_name: str = f"{field_name.capitalize()}Enum"
            field_type = Enum(enum_name, {v: v for v in enum_values})
        elif json_type == "object" and "properties" in field_props:
            field_type = json_schema_to_base_model(field_props)
        elif json_type == "array" and "items" in field_props:
            item_props = field_props["items"]
            if item_props.get("type") == "object":
                item_type: type[BaseModel] = json_schema_to_base_model(item_props)
            else:
                item_type: type = type_mapping.get(item_props.get("type"), Any)
            field_type = list[item_type]
        else:
            field_type = type_mapping.get(json_type, Any)

        # Handle default values and optionality
        default_value = field_props.get("default", ...)
        nullable = field_props.get("nullable", False)
        description = field_props.get("title", "")

        if nullable:
            field_type = Optional[field_type]

        if field_name not in required_fields:
            default_value = field_props.get("default", None)

        return field_type, Field(default_value, description=description)

    # Process each field
    for field_name, field_props in properties.items():
        model_fields[field_name] = process_field(field_name, field_props)

    return create_model(schema.get("title", "OptionalPageModel"), **model_fields)


class PageExtractor(BaseExtractor):
    """
    An extractor that pulls data from a single page.
    """

    max_concurrency: Annotated[
        int,
        "The maximum number of concurrent requests to make to the Gemini model.",
    ] = 3
    disable_tqdm: Annotated[
        bool,
        "Whether to disable the tqdm progress bar.",
    ] = False
    page_schema: Annotated[
        str,
        "The JSON schema to be extracted from the page.",
    ] = ""

    page_extraction_prompt = """You are an expert document analyst who reads documents and pulls data out in JSON format.
You will receive an image of a document page, the markdown representation of the page, and a JSON schema in pydantic format.
Your task is to extract the values in the schema from the page, and return them.  If a value in the schema does not exist on the page, return null to reflect that.

Some guidelines:
- If the schema has a field that is not present in the image, return null for that field.
- The confidence score should reflect both how confident you feel that the value in the schema exists in the image, and that you extracted the right value.

**Instructions:**
1. Carefully examine the provided page image.
2. Analyze the markdown representation of the page.
3. Analyze the JSON schema.
4. Write a short description of the fields in the schema, and the associated values in the image.
5. Extract the data in the schema that can be found in the image and output the data in JSON format.
6. Output an existence confidence score 1 to 5, where 1 is very low confidence that the values exist on the page, and 5 is very high confidence that the values exist on the page.
7. Output a value confidence score from 1 to 5, where 1 is very low confidence that the values are correct, and 5 is very high confidence that the values are correct.

**Example:**
Input:

Markdown
```markdown
| Make   | Sales |
|--------|-------|
| Honda  | 100   |
| Toyota | 200   |
```

Schema

```json
{'$defs': {'Cars': {'properties': {'make': {'title': 'Make', 'type': 'string'}, 'sales': {'title': 'Sales', 'type': 'integer'}, 'color': {'title': 'Color', 'type': 'string'}}, 'required': ['make', 'sales', 'color'], 'title': 'Cars', 'type': 'object'}}, 'properties': {'cars': {'items': {'$ref': '#/$defs/Cars'}, 'title': 'Cars', 'type': 'array'}}, 'required': ['cars'], 'title': 'CarsList', 'type': 'object'}
```

Output:

Description: The schema has a list of cars, each with a make, sales, and color. The image and markdown contain a table with 2 cars: Honda with 100 sales and Toyota with 200 sales. The color is not present in the table.

```json
{
    "cars": [
        {
            "make": "Honda",
            "sales": 100,
            "color": null
        },
        {
            "make": "Toyota",
            "sales": 200,
            "color": null
        }
    ]
}
```

Existence confidence: 5
Value confidence: 5

**Input:**

Markdown
```markdown
{page_md}
```

Schema
```json
{schema}
```
"""

    def __call__(
        self, document: Document, page: PageGroup, page_markdown: str, **kwargs
    ) -> Optional[ExtractionResult]:
        page_image = self.extract_image(document, page)
        if not self.page_schema:
            raise ValueError(
                "Page schema must be defined for structured extraction to work."
            )
        page_schema = json.loads(self.page_schema)
        optional_schema = make_all_optional(page_schema)

        prompt = self.page_extraction_prompt.replace(
            "{page_md}", page_markdown
        ).replace("{schema}", json.dumps(optional_schema))
        response = self.llm_service(prompt, page_image, page, PageExtractionSchema)

        if not response or any(
            [
                key not in response
                for key in [
                    "extracted_json",
                    "existence_confidence",
                    "value_confidence",
                ]
            ]
        ):
            page.update_metadata(llm_error_count=1)
            return None

        extracted_json = response["extracted_json"]

        OptionalPageModel = json_schema_to_base_model(optional_schema)
        try:
            OptionalPageModel.model_validate_json(extracted_json)
        except ValidationError as e:
            print(f"Validation error with extracted data: {e}")
            return None

        return ExtractionResult(
            extracted_data=json.loads(extracted_json),
            existence_confidence=response["existence_confidence"],
            value_confidence=response["value_confidence"],
        )


class PageExtractionSchema(BaseModel):
    description: str
    extracted_json: str
    existence_confidence: int
    value_confidence: int
