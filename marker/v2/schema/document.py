from typing import List

from pydantic import BaseModel

from marker.v2.schema.groups.page import PageGroup


class Document(BaseModel):
    filepath: str
    pages: List[PageGroup]