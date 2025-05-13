from pydantic import BaseModel


class ExtractionOutput(BaseModel):
    json: str
