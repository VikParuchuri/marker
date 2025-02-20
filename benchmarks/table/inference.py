from typing import List

import numpy as np
from bs4 import BeautifulSoup
import pypdfium2 as pdfium
from tqdm import tqdm
import base64
import tempfile

from benchmarks.table.gemini import gemini_table_rec
from marker.config.parser import ConfigParser
from marker.converters.table import TableConverter
from marker.models import create_model_dict
from marker.processors.llm.llm_table import LLMTableProcessor
from marker.processors.table import TableProcessor
from marker.renderers.json import JSONBlockOutput
from marker.schema.polygon import PolygonBox
from marker.util import matrix_intersection_area


def extract_tables(children: List[JSONBlockOutput]):
    tables = []
    for child in children:
        if child.block_type == 'Table':
            tables.append(child)
        elif child.children:
            tables.extend(extract_tables(child.children))
    return tables

def fix_table_html(table_html: str) -> str:
    marker_table_soup = BeautifulSoup(table_html, 'html.parser')
    tbody = marker_table_soup.find('tbody')
    if tbody:
        tbody.unwrap()
    for th_tag in marker_table_soup.find_all('th'):
        th_tag.name = 'td'
    for br_tag in marker_table_soup.find_all('br'):
        br_tag.replace_with(marker_table_soup.new_string(''))

    marker_table_html = str(marker_table_soup)
    marker_table_html = marker_table_html.replace("\n", " ")  # Fintabnet uses spaces instead of newlines
    return marker_table_html


def inference_tables(dataset, use_llm: bool, table_rec_batch_size: int | None, max_rows: int, use_gemini: bool):
    models = create_model_dict()
    config_parser = ConfigParser({'output_format': 'json', "use_llm": use_llm, "table_rec_batch_size": table_rec_batch_size, "disable_tqdm": True})
    total_unaligned = 0
    results = []

    iterations = len(dataset)
    if max_rows is not None:
        iterations = min(max_rows, len(dataset))

    for i in tqdm(range(iterations), desc='Converting Tables'):
        try:
            row = dataset[i]
            pdf_binary = base64.b64decode(row['pdf'])
            gt_tables = row['tables']  # Already sorted by reading order, which is what marker returns

            # Only use the basic table processors
            converter = TableConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=models,
                processor_list=[
                    "marker.processors.table.TableProcessor",
                    "marker.processors.llm.llm_table.LLMTableProcessor",
                ],
                renderer=config_parser.get_renderer()
            )

            with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as temp_pdf_file:
                temp_pdf_file.write(pdf_binary)
                temp_pdf_file.seek(0)
                marker_json = converter(temp_pdf_file.name).children

                doc = pdfium.PdfDocument(temp_pdf_file.name)
                page_image = doc[0].render(scale=96/72).to_pil()
                doc.close()

            if len(marker_json) == 0 or len(gt_tables) == 0:
                print(f'No tables detected, skipping...')
                total_unaligned += len(gt_tables)
                continue

            marker_tables = extract_tables(marker_json)
            marker_table_boxes = [table.bbox for table in marker_tables]
            page_bbox = marker_json[0].bbox

            if len(marker_tables) != len(gt_tables):
                print(f'Number of tables do not match, skipping...')
                total_unaligned += len(gt_tables)
                continue

            table_images = [
                page_image.crop(
                    PolygonBox.from_bbox(bbox)
                    .rescale(
                        (page_bbox[2], page_bbox[3]), (page_image.width, page_image.height)
                    ).bbox
                )
                for bbox
                in marker_table_boxes
            ]

            # Normalize the bboxes
            for bbox in marker_table_boxes:
                bbox[0] = bbox[0] / page_bbox[2]
                bbox[1] = bbox[1] / page_bbox[3]
                bbox[2] = bbox[2] / page_bbox[2]
                bbox[3] = bbox[3] / page_bbox[3]

            gt_boxes = [table['normalized_bbox'] for table in gt_tables]
            gt_areas = [(bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) for bbox in gt_boxes]
            marker_areas = [(bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) for bbox in marker_table_boxes]
            table_alignments = matrix_intersection_area(gt_boxes, marker_table_boxes)

            aligned_tables = []
            used_tables = set()
            unaligned_tables = set()
            for table_idx, alignment in enumerate(table_alignments):
                try:
                    max_area = np.max(alignment)
                    aligned_idx = np.argmax(alignment)
                except ValueError:
                    # No alignment found
                    unaligned_tables.add(table_idx)
                    continue

                if max_area <= .01:
                    # No alignment found
                    unaligned_tables.add(table_idx)
                    continue

                if aligned_idx in used_tables:
                    # Marker table already aligned with another gt table
                    unaligned_tables.add(table_idx)
                    continue

                # Gt table doesn't align well with any marker table
                gt_table_pct = gt_areas[table_idx] / max_area
                if not .85 < gt_table_pct < 1.15:
                    unaligned_tables.add(table_idx)
                    continue

                # Marker table doesn't align with gt table
                marker_table_pct = marker_areas[aligned_idx] / max_area
                if not .85 < marker_table_pct < 1.15:
                    unaligned_tables.add(table_idx)
                    continue

                gemini_html = ""
                if use_gemini:
                    try:
                        gemini_html = gemini_table_rec(table_images[aligned_idx])
                    except Exception as e:
                        print(f'Gemini failed: {e}')

                aligned_tables.append(
                    (marker_tables[aligned_idx], gt_tables[table_idx], gemini_html)
                )
                used_tables.add(aligned_idx)

            total_unaligned += len(unaligned_tables)

            for marker_table, gt_table, gemini_table in aligned_tables:
                gt_table_html = gt_table['html']

                # marker wraps the table in <tbody> which fintabnet data doesn't
                # Fintabnet doesn't use th tags, need to be replaced for fair comparison
                marker_table_html = fix_table_html(marker_table.html)
                gemini_table_html = fix_table_html(gemini_table)

                results.append({
                    "marker_table": marker_table_html,
                    "gt_table": gt_table_html,
                    "gemini_table": gemini_table_html
                })
        except pdfium.PdfiumError:
            print('Broken PDF, Skipping...')
            continue
    return results, total_unaligned