import json
from json import JSONDecodeError
from pathlib import Path

import datasets
from tqdm import tqdm


class Downloader:
    cache_path: Path = Path("cache")
    service: str

    def __init__(self, api_key, app_id, max_rows: int = 2200):
        self.cache_path.mkdir(exist_ok=True)
        self.max_rows = max_rows
        self.api_key = api_key
        self.app_id = app_id
        self.ds = datasets.load_dataset("datalab-to/marker_benchmark", split="train")

    def get_html(self, pdf_bytes):
        raise NotImplementedError

    def upload_ds(self):
        rows = []
        for file in self.cache_path.glob("*.json"):
            with open(file, "r") as f:
                data = json.load(f)
            rows.append(data)

        out_ds = datasets.Dataset.from_list(rows, features=datasets.Features({
            "md": datasets.Value("string"),
            "uuid": datasets.Value("string"),
            "time": datasets.Value("float"),
        }))
        out_ds.push_to_hub(f"datalab-to/marker_benchmark_{self.service}", private=True)

    def generate_data(self):
        max_rows = self.max_rows
        for idx, sample in tqdm(enumerate(self.ds), desc=f"Saving {self.service} results"):
            cache_file = self.cache_path / f"{idx}.json"
            if cache_file.exists():
                continue

            pdf_bytes = sample["pdf"]  # This is a single page PDF
            try:
                out_data = self.get_html(pdf_bytes)
            except JSONDecodeError as e:
                print(f"Error with sample {idx}: {e}")
                continue
            except Exception as e:
                print(f"Error with sample {idx}: {e}")
                continue
            out_data["uuid"] = sample["uuid"]

            with cache_file.open("w") as f:
                json.dump(out_data, f)

            if idx >= max_rows:
                break

    def __call__(self):
        self.generate_data()
        self.upload_ds()
