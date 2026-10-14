"""The public table JSON contract. Coordinates are pixels in a named crop."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class Region(StrictModel):
    region_id: str
    page: int = Field(ge=1)
    bbox: list[float] = Field(min_length=4, max_length=4)


class RowRegion(Region):
    r: int = Field(ge=0)


class ColumnRegion(Region):
    c: int = Field(ge=0)


class Figure(Region):
    labels: list[str] = Field(default_factory=list)
    description: str = ""
    src: str | None = None  # Filled by Marker after validating and saving the crop.


Flag = Literal[
    "inferred_span", "ditto_resolved", "formula_from_image", "dehyphenated",
    "continuation_line", "spans_page_break", "header_split_across_pages",
    "ambiguous_alignment", "unreadable", "text_mismatch", "shared_note",
]


class Cell(StrictModel):
    r: int = Field(ge=0)
    c: int = Field(ge=0)
    rowspan: int = Field(default=1, ge=1)
    colspan: int = Field(default=1, ge=1)
    role: Literal["header", "stub", "data", "group"]
    kind: Literal["text", "math", "mixed", "number", "dash", "figure", "empty"]
    text: str
    regions: list[Region]
    blocks: list[str]
    flags: list[Flag] = Field(default_factory=list)
    resolved_text: str | None = None
    num: float | None = None
    indent: int = Field(default=0, ge=0)
    figures: list[Figure] = Field(default_factory=list)


class Note(StrictModel):
    marker: str | None = None
    text: str
    inside_frame: bool
    blocks: list[str]
    regions: list[Region]


class Table(StrictModel):
    number: str | None = None
    title: str | None = None
    caption_raw: str = ""
    caption_blocks: list[str] = Field(default_factory=list)
    amendment_note: str | None = None
    amendment_blocks: list[str] = Field(default_factory=list)
    pages: list[int]
    regions: list[Region]
    truncated_start: bool
    truncated_end: bool
    n_rows: int = Field(ge=0, le=2000)
    n_cols: int = Field(ge=0, le=128)
    header_rows: int = Field(ge=0)
    row_regions: list[RowRegion]
    column_regions: list[ColumnRegion]
    cells: list[Cell]
    notes: list[Note] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class UnassignedBlock(StrictModel):
    id: str
    reason: str


class TableReconstruction(StrictModel):
    schema_version: Literal["1.1"]
    tables: list[Table]
    unassigned_blocks: list[UnassignedBlock]
    warnings: list[str]
