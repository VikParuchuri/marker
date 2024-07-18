import argparse
import json

import datasets
from surya.schema import LayoutResult, LayoutBox

from marker.benchmark.table import score_table
from marker.schema.bbox import rescale_bbox
from marker.schema.page import Page
from marker.tables.table import format_tables



def main():
    parser = argparse.ArgumentParser(description="Benchmark table conversion.")
    parser.add_argument("out_file", help="Output filename for results")
    parser.add_argument("--dataset", type=str, help="Dataset to use", default="vikp/table_bench")
    args = parser.parse_args()

    ds = datasets.load_dataset(args.dataset, split="train")

    results = []
    for i in range(len(ds)):
        row = ds[i]
        marker_page = Page(**json.loads(row["marker_page"]))
        table_bbox = row["table_bbox"]
        gpt4_table = json.loads(row["gpt_4_table"])["markdown_table"]

        # Counterclockwise polygon from top left
        table_poly = [
            [table_bbox[0], table_bbox[1]],
            [table_bbox[2], table_bbox[1]],
            [table_bbox[2], table_bbox[3]],
            [table_bbox[0], table_bbox[3]],
        ]

        # Remove all other tables from the layout results
        layout_result = LayoutResult(
            bboxes=[
                LayoutBox(
                    label="Table",
                    polygon=table_poly
                )
            ],
            segmentation_map="",
            image_bbox=marker_page.text_lines.image_bbox
        )

        marker_page.layout = layout_result
        format_tables([marker_page])

        table_blocks = [block for block in marker_page.blocks if block.block_type == "Table"]
        if len(table_blocks) != 1:
            continue

        table_block = table_blocks[0]
        table_md = table_block.lines[0].spans[0].text
        results.append({
            "score": score_table(table_md, gpt4_table),
            "arxiv_id": row["arxiv_id"],
            "page_idx": row["page_idx"],
            "marker_table": table_md,
            "gpt4_table": gpt4_table,
            "table_bbox": table_bbox
        })

    avg_score = sum([r["score"] for r in results]) / len(results)
    print(f"Evaluated {len(results)} tables, average score is {avg_score}.")

    with open(args.out_file, "w+") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()