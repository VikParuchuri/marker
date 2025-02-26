from surya.layout.schema import LayoutResult

from marker.builders.document import DocumentBuilder
from marker.builders.layout import LayoutBuilder
from marker.builders.line import LineBuilder
from marker.providers import ProviderOutput
import marker.schema.blocks
from marker.schema.groups.page import PageGroup
from marker.schema.polygon import PolygonBox
from tests.utils import convert_to_provider_output


def test_block_assignment():
    page_bbox = [0, 0, 500, 500]
    blocks = [
        (100, 0, 200, 500, marker.schema.blocks.Figure),
        (200, 0, 300, 500, marker.schema.blocks.Text)
    ]
    words = [
        (110, 0, 120, 10, "fig"),
        (110, 10, 120, 20, "fig"),
        (110, 20, 120, 30, "fig"),

        (220, 0, 230, 10, "intext"),
        (220, 10, 230, 20, "intext"),
        (220, 20, 230, 30, "intext"),

        (150, 30, 250, 40, "both"),
        (150, 40, 250, 50, "both"),
        (150, 50, 250, 60, "both"),

        (180, 60, 280, 70, "mosttext"),
        (180, 70, 280, 80, "mosttext"),
        (180, 80, 280, 90, "mosttext"),

        (120, 90, 220, 100, "mostfig"),
        (120, 100, 220, 110, "mostfig"),
        (120, 110, 220, 120, "mostfig"),
    ]
    block_ctr = 0
    def get_counter():
        nonlocal block_ctr
        o = block_ctr
        block_ctr += 1
        return o
    page_group = PageGroup(polygon=PolygonBox.from_bbox(page_bbox),
                           children=[
                               block_cls(polygon=PolygonBox.from_bbox([xmin, ymin, xmax, ymax]),
                                   page_id=0,
                                   block_id=get_counter())
                               for xmin, ymin, xmax, ymax, block_cls in blocks
                           ])

    provider_outputs = [
        convert_to_provider_output([word], page_bbox=[0, 0, 500, 500], get_counter=get_counter) for word in words
    ]


    assert not page_group.children[0].structure, "figure's structure should begin with nothing in it"
    assert not page_group.children[1].structure, "text's structure should begin with nothing in it"

    page_group.merge_blocks(provider_outputs, text_extraction_method='custom')

    assert len(page_group.children[0].structure) == 3, "figure should have just 3 words"
    assert len(page_group.children[1].structure) == 12, "text should have the remaining 12 words"

