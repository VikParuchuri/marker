import os
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
from concurrent.futures import ThreadPoolExecutor
from pypdfium2._helpers.misc import PdfiumError

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


@click.command(help="Benchmark Table to HTML Conversion")
@click.argument("out_file", type=str)
@click.option("--dataset", type=str, default="datalab-to/fintabnet-test", help="Dataset to use")
@click.option("--max_rows", type=int, default=None, help="Maximum number of PDFs to process")
def main(out_file: str, dataset: str, max_rows: int):
    models = create_model_dict()
    config_parser = ConfigParser({'output_format': 'html'})
    start = time.time()


    dataset = datasets.load_dataset(dataset, split='train')
    dataset = dataset.shuffle(seed=0)

    iterations = len(dataset)
    if max_rows is not None:
        iterations = min(max_rows, len(dataset))

    results = []
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
                marker_table_html = converter(temp_pdf_file.name).html

            marker_table_soup = BeautifulSoup(marker_table_html, 'html.parser')
            marker_detected_tables = marker_table_soup.find_all('table')
            if len(marker_detected_tables)==0:
                print(f'No tables detected, skipping...')
            
            for marker_table_soup, gt_table in zip(marker_detected_tables, gt_tables):
                gt_table_html = gt_table['html']
                
                #marker wraps the table in <tbody> which fintabnet data doesn't
                marker_table_soup.find('tbody').unwrap()
                #Fintabnet doesn't use th tags, need to be replaced for fair comparison
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

    print(f"Total time: {time.time() - start}")

    with ThreadPoolExecutor(max_workers=16) as executor:
        results = list(tqdm(executor.map(update_teds_score, results), desc='Computing alignment scores', total=len(results)))
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