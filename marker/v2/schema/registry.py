from typing import Dict, Type, TypeVar

from marker.v2.schema import BlockTypes
from marker.v2.schema.blocks import Block, Caption, Code, Equation, Figure, \
    Footnote, Form, Handwriting, InlineMath, \
    ListItem, PageFooter, PageHeader, Picture, \
    SectionHeader, Table, TableOfContents, \
    Text
from marker.v2.schema.document import Document
from marker.v2.schema.groups import FigureGroup, ListGroup, PageGroup, \
    PictureGroup, TableGroup
from marker.v2.schema.text import Line, Span

BLOCK_REGISTRY: Dict[str, Type[Block]] = {
    BlockTypes.Line: Line,
    BlockTypes.Span: Span,
    BlockTypes.FigureGroup: FigureGroup,
    BlockTypes.TableGroup: TableGroup,
    BlockTypes.ListGroup: ListGroup,
    BlockTypes.PictureGroup: PictureGroup,
    BlockTypes.Page: PageGroup,
    BlockTypes.Caption: Caption,
    BlockTypes.Code: Code,
    BlockTypes.Figure: Figure,
    BlockTypes.Footnote: Footnote,
    BlockTypes.Form: Form,
    BlockTypes.Equation: Equation,
    BlockTypes.Handwriting: Handwriting,
    BlockTypes.TextInlineMath: InlineMath,
    BlockTypes.ListItem: ListItem,
    BlockTypes.PageFooter: PageFooter,
    BlockTypes.PageHeader: PageHeader,
    BlockTypes.Picture: Picture,
    BlockTypes.SectionHeader: SectionHeader,
    BlockTypes.Table: Table,
    BlockTypes.Text: Text,
    BlockTypes.TableOfContents: TableOfContents,
    BlockTypes.Document: Document,
}

T = TypeVar('T')


def get_block_cls(block_cls: T) -> T:
    return BLOCK_REGISTRY.get(block_cls.model_fields['block_type'].default, block_cls)


assert len(BLOCK_REGISTRY) == len(BlockTypes)
assert all([v.model_fields['block_type'].default == k for k, v in BLOCK_REGISTRY.items()])
