from marker.v2.schema.blocks.caption import Caption
from marker.v2.schema.blocks.code import Code
from marker.v2.schema.blocks.figure import Figure
from marker.v2.schema.blocks.footnote import Footnote
from marker.v2.schema.blocks.form import Form
from marker.v2.schema.blocks.equation import Equation
from marker.v2.schema.blocks.handwriting import Handwriting
from marker.v2.schema.blocks.inlinemath import InlineMath
from marker.v2.schema.blocks.listitem import ListItem
from marker.v2.schema.blocks.pagefooter import PageFooter
from marker.v2.schema.blocks.pageheader import PageHeader
from marker.v2.schema.blocks.picture import Picture
from marker.v2.schema.blocks.sectionheader import SectionHeader
from marker.v2.schema.blocks.table import Table
from marker.v2.schema.blocks.text import Text
from marker.v2.schema.blocks.toc import TableOfContents

LAYOUT_BLOCK_REGISTRY = {
    b.block_type: b for b in
    [Caption, Code, Figure, Footnote, Form, Equation, Handwriting, InlineMath, ListItem, PageFooter, PageHeader, Picture, SectionHeader, Table, Text, TableOfContents]
}