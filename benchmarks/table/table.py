import os
from typing import List

import numpy as np

from marker.renderers.json import JSONOutput, JSONBlockOutput

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Transformers uses .isin for a simple op, which is not supported on MPS

import base64
import time
import datasets
from tqdm import tqdm
import tempfile
import click
from tabulate import tabulate
import json
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from pypdfium2._helpers.misc import PdfiumError
from marker.util import matrix_intersection_area

from marker.config.parser import ConfigParser
from marker.converters.table import TableConverter
from marker.models import create_model_dict

from scoring import wrap_table_html, similarity_eval_html

def update_teds_score(result):
    prediction, ground_truth = result['marker_table'], result['gt_table']
    prediction, ground_truth = wrap_table_html(prediction), wrap_table_html(ground_truth)
    score = similarity_eval_html(prediction, ground_truth)
    result.update({'score':score})
    return result


def extract_tables(children: List[JSONBlockOutput]):
    tables = []
    for child in children:
        if child.block_type == 'Table':
            tables.append(child)
        elif child.children:
            tables.extend(extract_tables(child.children))
    return tables


@click.command(help="Benchmark Table to HTML Conversion")
@click.argument("out_file", type=str)
@click.option("--dataset", type=str, default="datalab-to/fintabnet-test", help="Dataset to use")
@click.option("--max_rows", type=int, default=None, help="Maximum number of PDFs to process")
@click.option("--max_workers", type=int, default=16, help="Maximum number of workers to use")
def main(out_file: str, dataset: str, max_rows: int, max_workers: int):
    models = create_model_dict()
    config_parser = ConfigParser({'output_format': 'json'})
    start = time.time()


    dataset = datasets.load_dataset(dataset, split='train')
    dataset = dataset.shuffle(seed=0)

    iterations = len(dataset)
    if max_rows is not None:
        iterations = min(max_rows, len(dataset))

    results = []
    total_unaligned = 0
    for i in tqdm(range(iterations), desc='Converting Tables'):
        try:
            row = dataset[i]
            pdf_binary = base64.b64decode(row['pdf'])
            gt_tables = row['tables']       #Already sorted by reading order, which is what marker returns

            converter = TableConverter(
                config=config_parser.generate_config_dict(),
                artifact_dict=models,
                processor_list=config_parser.get_processors(),
                renderer=config_parser.get_renderer()
            )

            with tempfile.NamedTemporaryFile(suffix=".pdf", mode="wb") as temp_pdf_file:
                temp_pdf_file.write(pdf_binary)
                temp_pdf_file.seek(0)
                tqdm.disable = True
                marker_json = converter(temp_pdf_file.name).children
                tqdm.disable = False

            if len(marker_json) == 0 or len(gt_tables) == 0:
                print(f'No tables detected, skipping...')
                total_unaligned += len(gt_tables)
                continue

            marker_tables = extract_tables(marker_json)
            marker_table_boxes = [table.bbox for table in marker_tables]
            page_bbox = marker_json[0].bbox

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

                if aligned_idx in used_tables:
                    # Marker table already aligned with another gt table
                    unaligned_tables.add(table_idx)
                    continue

                # Gt table doesn't align well with any marker table
                gt_table_pct = gt_areas[table_idx] / max_area
                if not .75 < gt_table_pct < 1.25:
                    unaligned_tables.add(table_idx)
                    continue

                # Marker table doesn't align with gt table
                marker_table_pct = marker_areas[aligned_idx] / max_area
                if not .75 < marker_table_pct < 1.25:
                    unaligned_tables.add(table_idx)
                    continue

                aligned_tables.append(
                    (marker_tables[aligned_idx], gt_tables[table_idx])
                )
                used_tables.add(aligned_idx)

            total_unaligned += len(unaligned_tables)
            
            for marker_table, gt_table in aligned_tables:
                gt_table_html = gt_table['html']

                #marker wraps the table in <tbody> which fintabnet data doesn't
                #Fintabnet doesn't use th tags, need to be replaced for fair comparison
                marker_table_soup = BeautifulSoup(marker_table.html, 'html.parser')
                marker_table_soup.find('tbody').unwrap()
                for th_tag in marker_table_soup.find_all('th'):
                    th_tag.name = 'td'
                marker_table_html = str(marker_table_soup)

                results.append({
                    "marker_table": marker_table_html,
                    "gt_table": gt_table_html
                })
        except PdfiumError:
            print('Broken PDF, Skipping...')
            continue

    print(f"Total time: {time.time() - start}.")
    print(f"Could not align {total_unaligned} tables from fintabnet.")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(
            tqdm(
                executor.map(update_teds_score, results), desc='Computing alignment scores', total=len(results)
            )
        )
    avg_score = sum([r["score"] for r in results]) / len(results)

    headers = ["Avg score", "Total tables"]
    data = [f"{avg_score:.3f}", len(results)]
    table = tabulate([data], headers=headers, tablefmt="github")
    print(table)
    print("Avg score computed by comparing marker predicted HTML with original HTML")

    with open(out_file, "w+") as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()