import io
import os
from itertools import repeat
from tkinter import Image

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Transformers uses .isin for a simple op, which is not supported on MPS

from typing import List
import numpy as np
import base64
import time
import datasets
from tqdm import tqdm
import tempfile
import click
from tabulate import tabulate
import json
from bs4 import BeautifulSoup
from concurrent.futures import ProcessPoolExecutor
from pypdfium2._helpers.misc import PdfiumError
import pypdfium2 as pdfium
from marker.util import matrix_intersection_area
from marker.renderers.json import JSONOutput, JSONBlockOutput

from marker.config.parser import ConfigParser
from marker.converters.table import TableConverter
from marker.models import create_model_dict

from scoring import wrap_table_html, similarity_eval_html
from gemini import gemini_table_rec
from input_word_bboxes import GroundTruthPagesForcer, ChangedTableConverter, convert_to_page

def update_teds_score(result, prefix: str = "marker"):
    prediction, ground_truth = result[f'{prefix}_table'], result['gt_table']
    prediction, ground_truth = wrap_table_html(prediction), wrap_table_html(ground_truth)
    score = similarity_eval_html(prediction, ground_truth)
    result.update({f'{prefix}_score':score})
    return result


def extract_tables(children: List[JSONBlockOutput]):
    tables = []
    for child in children:
        if child.block_type == 'Table':
            tables.append(child)
        elif child.children:
            tables.extend(extract_tables(child.children))
    return tables

def fintabnet_form_tbody(marker_table_soup: BeautifulSoup) -> str:
    #marker wraps the table in <tbody> which fintabnet data doesn't
    #Fintabnet doesn't use th tags, need to be replaced for fair comparison. Not true for synthtabnet
    tbody = marker_table_soup.find('tbody')
    if tbody:
        tbody.unwrap()
    for th_tag in marker_table_soup.find_all('th'):
        th_tag.name = 'td'
    return str(marker_table_soup)

def synthtabnet_form_tbody(marker_table_soup: BeautifulSoup):
    """
    Used for synthtabnet
    """
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
    return str(marker_table_soup)


@click.command(help="Benchmark Table to HTML Conversion")
@click.argument("out_file", type=str)
@click.option("--dataset", type=str, default="datalab-to/fintabnet-test", help="Dataset to use")
@click.option("--max_rows", type=int, default=None, help="Maximum number of PDFs to process")
@click.option("--max_workers", type=int, default=16, help="Maximum number of workers to use")
@click.option("--use_llm", is_flag=True, help="Use LLM for improving table recognition.")
@click.option("--table_rec_batch_size", type=int, default=None, help="Batch size for table recognition.")
@click.option("--use_gemini", is_flag=True, help="Evaluate Gemini for table recognition.")
def main(
        out_file: str,
        dataset: str,
        max_rows: int,
        max_workers: int,
        use_llm: bool,
        table_rec_batch_size: int | None,
        use_gemini: bool = False
): 
    _process(out_file, dataset, max_rows, max_workers, use_llm, table_rec_batch_size, use_gemini)

def _process(
        out_file: str,
        dataset: str,
        max_rows: int,
        max_workers: int,
        use_llm: bool,
        table_rec_batch_size: int | None,
        use_gemini: bool = False
):
    models = create_model_dict()
    config_parser = ConfigParser({
        "output_format": 'json', 
        "use_llm": use_llm, 
        "table_rec_batch_size": table_rec_batch_size, 
        "force_layout_block": 'Table'
    })
    start = time.time()

    dataset = datasets.load_from_disk(dataset)
    # dataset = datasets.load_dataset(dataset, split='train')
    dataset = dataset.shuffle(seed=0)

    iterations = len(dataset)
    if max_rows is not None:
        iterations = min(max_rows, len(dataset))

    results = []
    total_unaligned = 0

    gt_forcer = GroundTruthPagesForcer()

    converter = ChangedTableConverter(
        config={
            **config_parser.generate_config_dict(),
            "document_ocr_threshold": 0 # never perform OCR for evaluation: we know the ground truth
        },
        artifact_dict={
            '_gt_forcer': gt_forcer,
            **models
        },
        processor_list=config_parser.get_processors(),
        renderer=config_parser.get_renderer()
    )
    for i in tqdm(range(iterations), desc='Converting Tables'):
        try:
            row = dataset[i]
            # pdf_binary = base64.b64decode(row['pdf'])
            # gt_tables = row['tables']       #Already sorted by reading order, which is what marker returnss

            gt_tables = [{
                'normalized_bbox': [0, 0, 1, 1],
                'html': row['html']
            }]

            with tempfile.NamedTemporaryFile(suffix=".png", mode="wb", delete=False) as temp_png_file:
                filename = row['filename']
                bytesio = io.BytesIO()
                page_image = row['image'] # type: Image.Image
                page_image.save(bytesio, format="PNG")

                temp_png_file.write(bytesio.getvalue())
                temp_png_file.seek(0)

                bboxes = row['word_bboxes']
                words = row['words']
                good = [i for i, word in enumerate(words) if word] # allow only non-empty words
                bboxes = [bboxes[i] for i in good]
                words = [words[i] for i in good]

                image_bbox = [0, 0, page_image.width, page_image.height]
                gt_forcer.forced_pages = [convert_to_page(bboxes, words, image_bbox, 0)]

                tqdm.disable = True
                marker_json = converter(temp_png_file.name).children
                tqdm.disable = False

                temp_png_file.close()
                os.unlink(temp_png_file.name)

            if len(marker_json) == 0 or len(gt_tables) == 0:
                print(f'No tables detected, skipping...')
                total_unaligned += len(gt_tables)
                continue

            marker_tables = extract_tables(marker_json)
            marker_table_boxes = [table.bbox for table in marker_tables]
            page_bbox = marker_json[0].bbox
            w_scaler, h_scaler = page_image.width / page_bbox[2], page_image.height / page_bbox[3]
            table_images = [page_image.crop([bbox[0] * w_scaler, bbox[1] * h_scaler, bbox[2] * w_scaler, bbox[3] * h_scaler]) for bbox in marker_table_boxes]

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

                gemini_html = ""
                if use_gemini:
                    gemini_html = gemini_table_rec(table_images[aligned_idx])

                aligned_tables.append(
                    (marker_tables[aligned_idx], gt_tables[table_idx], gemini_html)
                )
                used_tables.add(aligned_idx)

            total_unaligned += len(unaligned_tables)
            
            for marker_table, gt_table, gemini_table in aligned_tables:
                gt_table_html = gt_table['html']

                #marker wraps the table in <tbody> which fintabnet data doesn't
                #Fintabnet doesn't use th tags, need to be replaced for fair comparison. Not true for synthtabnet
                marker_table_soup = BeautifulSoup(marker_table.html, 'html.parser')
                marker_table_html = synthtabnet_form_tbody(marker_table_soup)
                marker_table_html = marker_table_html.replace("<br>", " ") # Fintabnet uses spaces instead of newlines
                marker_table_html = marker_table_html.replace("\n", " ") # Fintabnet uses spaces instead of newlines
                gemini_table_html = gemini_table.replace("\n", " ") # Fintabnet uses spaces instead of newlines

                results.append({
                    "marker_table": marker_table_html,
                    "gt_table": gt_table_html,
                    "gemini_table": gemini_table_html
                })
        except PdfiumError:
            print('Broken PDF, Skipping...')
            continue

    print(f"Total time: {time.time() - start}.")
    print(f"Could not align {total_unaligned} tables from fintabnet.")

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        marker_results = list(
            tqdm(
                executor.map(update_teds_score, results), desc='Computing alignment scores', total=len(results)
            )
        )

    avg_score = sum([r["marker_score"] for r in marker_results]) / len(marker_results)
    headers = ["Avg score", "Total tables"]
    data = [f"{avg_score:.3f}", len(marker_results)]
    gemini_results = None
    if use_gemini:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            gemini_results = list(
                tqdm(
                    executor.map(update_teds_score, results, repeat("gemini")), desc='Computing Gemini scores',
                    total=len(results)
                )
            )
        avg_gemini_score = sum([r["gemini_score"] for r in gemini_results]) / len(gemini_results)
        headers.append("Avg Gemini score")
        data.append(f"{avg_gemini_score:.3f}")

    table = tabulate([data], headers=headers, tablefmt="github")
    print(table)
    print("Avg score computed by comparing marker predicted HTML with original HTML")

    results = {
        "marker": marker_results,
        "gemini": gemini_results
    }

    with open(out_file, "w+") as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    # main()
    _process("experiments/synthtabnet_sparse_test.json", "experiments/synthtabnet_sparse_test", 3, 1, False, None, False)