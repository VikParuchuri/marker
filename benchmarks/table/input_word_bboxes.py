# marker_single experiments/pdf/tiny.pdf --output_dir experiments/out
# marker_single experiments/pdf/tiny.pdf --output_dir experiments/out --converter_cls marker.converters.table.TableConverter --debug --output_format json

import os
import tempfile
from typing import Tuple
from marker.builders.document import DocumentBuilder
from marker.builders.ocr import OcrBuilder
from marker.processors import BaseProcessor
from marker.processors.llm.llm_complex import LLMComplexRegionProcessor
from marker.processors.llm.llm_form import LLMFormProcessor
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.llm.llm_table_merge import LLMTableMergeProcessor
from marker.processors.table import TableProcessor
from marker.providers import ProviderOutput
from marker.providers.image import ImageProvider
from marker.schema.polygon import PolygonBox
from marker.schema.text.line import Line
from marker.schema.text.span import Span
from marker.schema.blocks.base import Block
import pdftext.schema

from marker.converters.table import TableConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered


# unused
def _convert_to_provider_output(words, page_id=0):
    outputs = []

    for word in words:
        x0, y0, x1, y1, text = word

        # Create the PolygonBox
        polygon = PolygonBox(polygon=[[x0, y0], [x1, y0], [x1, y1], [x0, y1]])

        # Create the Line
        line = Line(
            polygon=polygon,
            # block_description="A line of text.",
            source="layout",
            page_id=page_id
        )

        # Create the Span
        span = Span(
            polygon=polygon,
            # block_description="A span of text inside a line.",
            text=text,
            font="DefaultFont",
            font_weight=400,
            font_size=12.0,
            minimum_position=0,
            maximum_position=100,
            formats=["plain"],
            source="layout",
            page_id=page_id
        )

        # Combine into ProviderOutput
        provider_output = ProviderOutput(line=line, spans=[span])
        outputs.append(provider_output)

    return outputs

# Convert the input format to the desired page format
def convert_to_page(word_bboxes, words, page_bbox, page_number): 
    blocks = []
    block_lines = []

    # for word in words:
    for vec4, text in zip(word_bboxes, words):
        x0, y0, x1, y1 = vec4
        word_bbox = pdftext.schema.Bbox(bbox=[x0, y0, x1, y1])

        # Create Char entries (assuming each character has uniform bbox)
        chars = []
        char_width = (x1 - x0) / len(text)
        for i, char in enumerate(text):
            char_bbox = pdftext.schema.Bbox(bbox=[x0 + i * char_width, y0, x0 + (i + 1) * char_width, y1])
            chars.append(pdftext.schema.Char(
                bbox=char_bbox,
                char=char,
                rotation=0,
                font={"name": "DefaultFont"},
                char_idx=i
            ))

        # Create the Span
        span = pdftext.schema.Span(
            bbox=word_bbox,
            text=text,
            font={"name": "DefaultFont"},
            chars=chars,
            char_start_idx=0,
            char_end_idx=len(text) - 1,
            rotation=0,
            url=""
        )

        # Create the Line
        line = pdftext.schema.Line(
            spans=[span],
            bbox=word_bbox,
            rotation=0
        )

        block_lines.append(line)

    # Create the Block
    block = pdftext.schema.Block(
        lines=block_lines,
        bbox=page_bbox,
        rotation=0
    )
    blocks.append(block)

    # Create the Page
    page = pdftext.schema.Page(
        page=page_number,
        bbox=page_bbox,
        width=page_bbox[2] - page_bbox[0],
        height=page_bbox[3] - page_bbox[1],
        blocks=blocks,
        rotation=0,
        refs=[]
    )

    return page

from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor, OCRResult
from surya.table_rec import TableRecPredictor

class GroundTruthPagesForcer:
    def __init__(self):
        # debug data
        self.forced_pages = None # [convert_to_page(get_raw_test_data(), [0, 0, 612.0, 792.0], 0)]
    def __call__(self, filepath):
        return self.forced_pages

class ChangedTableProcessor(TableProcessor):

    def __init__(
        self,
        detection_model: DetectionPredictor,
        recognition_model: RecognitionPredictor,
        table_rec_model: TableRecPredictor,
        config=None,
        _gt_forcer: GroundTruthPagesForcer=None,
    ):
        super().__init__(detection_model=detection_model, recognition_model=recognition_model, table_rec_model=table_rec_model, config=config)
        self.detection_model = detection_model
        self.recognition_model = recognition_model
        self.table_rec_model = table_rec_model
        self._gt_forcer = _gt_forcer

    def assign_pdftext_lines(self, extract_blocks: list[dict], filepath):
        forced_pages = self._gt_forcer(filepath)
        self.assign_forced_lines(extract_blocks, forced_pages)

    def assign_forced_lines(self, extract_blocks: list[dict], forced_pages):
        table_inputs = []
        unique_pages = list(set([t["page_id"] for t in extract_blocks]))
        if len(unique_pages) == 0:
            return

        for page in unique_pages:
            tables = []
            img_size = None
            for block in extract_blocks:
                if block["page_id"] == page:
                    tables.append(block["table_bbox"])
                    img_size = block["img_size"]

            table_inputs.append({
                "tables": tables,
                "img_size": img_size
            })
        
        # NOTE: added this method
        def table_output(filepath, table_inputs, page_range=unique_pages):
            # mock forced_pages
            pages = []
            for i in page_range:
                pages.append(forced_pages[i])
            

            from pdftext.extraction import table_cell_text
            out_tables = []
            for page, table_input in zip(forced_pages, table_inputs):
                tables = table_cell_text(table_input["tables"], page, table_input["img_size"])
                assert len(tables) == len(table_input["tables"]), "Number of tables and table inputs must match"
                out_tables.append(tables)
            return out_tables
        cell_text = table_output(None, table_inputs, page_range=unique_pages)

        assert len(cell_text) == len(unique_pages), "Number of pages and table inputs must match"
        
        for pidx, (page_tables, pnum) in enumerate(zip(cell_text, unique_pages)):
            table_idx = 0
            for block in extract_blocks:
                if block["page_id"] == pnum:
                    block["table_text_lines"] = page_tables[table_idx]
                    table_idx += 1
            assert table_idx == len(page_tables), "Number of tables and table inputs must match"

    
class ChangedTableConverter(TableConverter):
    default_processors: Tuple[BaseProcessor, ...] = (
        ChangedTableProcessor, # NOTE: changed this line
        LLMTableProcessor,
        LLMTableMergeProcessor,
        LLMFormProcessor,
        LLMComplexRegionProcessor,
    )
    
    # def provider_from_filepath(self, filepath):
        # return ChangedProvider # override
