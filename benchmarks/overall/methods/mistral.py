import datasets

from benchmarks.overall.methods import BaseMethod, BenchmarkResult


class MistralMethod(BaseMethod):
    mistral_ds: datasets.Dataset = None

    def __call__(self, sample) -> BenchmarkResult:
        uuid = sample["uuid"]
        data = None
        for row in self.mistral_ds:
            if str(row["uuid"]) == str(uuid):
                data = row
                break
        if not data:
            raise ValueError(f"Could not find data for uuid {uuid}")

        return {
            "markdown": data["md"],
            "time": data["time"]
        }