"""
Detect tables when the pdf is not available
"""


from functools import partialmethod
import io
import os
import tempfile
from typing import Tuple

from bs4 import BeautifulSoup
from tqdm import tqdm
from benchmarks.table.gemini import gemini_table_rec, prompt_with_header
from benchmarks.table.inference import FinTabNetBenchmark
from marker.processors import BaseProcessor
from marker.processors.llm.llm_complex import LLMComplexRegionProcessor
from marker.processors.llm.llm_form import LLMFormProcessor
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.llm.llm_table_merge import LLMTableMergeProcessor
from marker.processors.table import TableProcessor
from marker.converters.table import TableConverter

import pdftext.schema
from surya.detection import DetectionPredictor
from surya.recognition import RecognitionPredictor
from surya.table_rec import TableRecPredictor

def convert_to_page(word_bboxes: list[tuple], words: list[str], page_bbox: tuple, page_number: int): 
    """Converts word bboxes into a pdftext Page object"""
    blocks = []
    block_lines = []

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

        line = pdftext.schema.Line(
            spans=[span],
            bbox=word_bbox,
            rotation=0
        )

        block_lines.append(line)

    block = pdftext.schema.Block(
        lines=block_lines,
        bbox=page_bbox,
        rotation=0
    )
    blocks.append(block)

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

class SynthTabNetBenchmark(FinTabNetBenchmark):
    gt_forcer: GroundTruthPagesForcer
    def get_converter(self, models, config_parser, **kwargs):
        config_parser.cli_options['force_layout_block'] = 'Table'
        self.gt_forcer = GroundTruthPagesForcer()

        return ChangedTableConverter(
            config={
                **config_parser.generate_config_dict(),
                "document_ocr_threshold": 0 # never perform OCR for evaluation: we know the ground truth
            },
            artifact_dict={
                '_gt_forcer': self.gt_forcer,
                **models
            },
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer()
        )

    def synthtabnet_page_with_gt_words(self, row, page_image):
        bboxes = row['word_bboxes']
        words = row['words']
        good = [i for i, word in enumerate(words) if word] # allow only non-empty words
        bboxes = [bboxes[i] for i in good]
        words = [words[i] for i in good]

        image_bbox = [0, 0, page_image.width, page_image.height]
        return convert_to_page(bboxes, words, image_bbox, 0)

    def extract_tables_from_doc(self, converter, row):
        original_tqdm = tqdm.__init__

        # https://stackoverflow.com/a/23212515
        manual_management = os.name == 'nt' 
        with tempfile.NamedTemporaryFile(suffix=".png", mode="wb", delete=not manual_management) as temp_png_file:

            bytesio = io.BytesIO()
            page_image = row['image'] # PIL.Image.Image
            page_image.save(bytesio, format="PNG")

            temp_png_file.write(bytesio.getvalue())
            temp_png_file.seek(0)

            self.gt_forcer.forced_pages = [
                self.synthtabnet_page_with_gt_words(row, page_image)
            ]

            tqdm.__init__ = partialmethod(tqdm.__init__, disable=True)
            marker_json = converter(temp_png_file.name).children # word bboxes are ingested by way of "gt_forcer"
            tqdm.__init__ = original_tqdm # enable

            if manual_management:
                temp_png_file.close()
                os.remove(temp_png_file.name)
        return marker_json, page_image

    def extract_gt_tables(self, row, **kwargs):
        return [{
            'normalized_bbox': [0, 0, 1, 1],
            'html': row['html']
        }]

    def extract_gemini_tables(self, row, image, **kwargs):
        gemini_table = gemini_table_rec(image, prompt=prompt_with_header)
        # gemini_table_html = self.postprocess_marker_to_html(gemini_table) # put through same th --> thead/tbody pipeline
        return gemini_table


    def postprocess_marker_to_html(self, marker_table: str):
        marker_table_soup = BeautifulSoup(marker_table, 'html.parser')
        # Synthtabnet uses thead and tbody tags
        # Marker uses th tags
        thead = marker_table_soup.new_tag('thead')
        tbody = marker_table_soup.new_tag('tbody')
        in_thead = True

        for tr in marker_table_soup.find_all('tr'):
            if in_thead and all(th_tag.name == 'th' for th_tag in tr.find_all()):
                thead.append(tr)
            else:
                in_thead = False
                tbody.append(tr)

        # create anew
        marker_table_soup.clear()
        marker_table_soup.append(thead)
        marker_table_soup.append(tbody)

        for th_tag in marker_table_soup.find_all('th'):
            th_tag.name = 'td'
        marker_table_html = str(marker_table_soup)
        marker_table_html = marker_table_html.replace("<br>", " ") # Fintabnet uses spaces instead of newlines
        marker_table_html = marker_table_html.replace("\n", " ")
        return marker_table_html

    def postprocess_gemini_to_html(self, gemini_table: str) -> str:
        gemini_table = super().postprocess_gemini_to_html(gemini_table)
        gemini_table = gemini_table.replace("<table>", "").replace("</table>", "")
        return gemini_table

    def construct_row_result(self, row, gt_table, marker_table, gemini_table, **kwargs):
        return {
            "filename": row['filename'],
            "dataset_variant": row.get('dataset_variant', row.get('dataset')),
            "marker_table": marker_table,
            "gt_table": gt_table,
            "gemini_table": gemini_table
        }