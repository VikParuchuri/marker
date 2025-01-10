import os
import time
import datasets
from tqdm import tqdm
import tempfile
import click
from tabulate import tabulate
import json
from bs4 import BeautifulSoup

os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"  # Transformers uses .isin for a simple op, which is not supported on MPS

from marker.config.parser import ConfigParser
from marker.converters.table import TableConverter
from marker.models import create_model_dict
from marker.output import save_output

from scoring import batched_TEDS


@click.command(help="Benchmark Table to HTML Conversion")
@click.argument("out_file", type=str)
@click.option("--dataset", type=str, default="tarun-menta/fintabnet-html-test", help="Dataset to use")
@click.option("--max", type=int, default=None, help="Max number of tables to process")
def main(out_file, dataset, max):
    models = create_model_dict()
    config_parser = ConfigParser({})
    start = time.time()

    converter = TableConverter(
        config=config_parser.generate_config_dict(),
        artifact_dict=models,
        processor_list=config_parser.get_processors(),
        renderer='marker.renderers.html.HTMLRenderer'
    )

    dataset = datasets.load_dataset(dataset, split='train')
    dataset = dataset.shuffle(seed=0)

    iterations = len(dataset)
    if max is not None:
        iterations = min(max, len(dataset))

    results = []
    for i in tqdm(range(iterations), desc='Converting Tables'):
        row = dataset[i]
        table_img = row['highres_table_img']
        with tempfile.NamedTemporaryFile(suffix=".png", mode="wb+") as temp_img_file:
            table_img.save(temp_img_file)
            temp_img_file.seek(0)
            filename = temp_img_file.name

            marker_table_html = converter(filename).html
            marker_table_soup = BeautifulSoup(marker_table_html, 'html.parser')

            #marker wraps the table in <tbody> which fintabnet data doesn't
            marker_table_soup.find('tbody').unwrap()    

            #Fintabnet doesn't use th tags, need to be replaced for fair comparison
            for th_tag in marker_table_soup.find_all('th'):
                th_tag.name = 'td'

            marker_table_html = str(marker_table_soup)

        results.append({
            "marker_table": marker_table_html,
            "gt_table": row['orig_html']
        })

    scores = batched_TEDS([r['gt_table'] for r in results], [r['marker_table'] for r in results])
    for result, score in zip(results, scores):
        result.update({'score': score})

    avg_score = sum([r["score"] for r in results]) / len(results)

    total_time = time.time() - start
    print(f"Total time: {time.time() - start}")
    headers = ["Avg score", "Time per table", "Total tables"]
    data = [f"{avg_score:.3f}", f"{total_time / iterations:.3f}", iterations]
    table = tabulate([data], headers=headers, tablefmt="github")
    print(table)
    print("Avg score computed by comparing tabled predicted HTML with original HTML")

    with open(out_file, "w+") as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()