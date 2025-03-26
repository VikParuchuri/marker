import io
import time

import requests

from benchmarks.overall.download.base import Downloader


class LlamaParseDownloader(Downloader):
    service = "llamaparse"

    def get_html(self, pdf_bytes):
        rand_name = str(time.time()) + ".pdf"
        start = time.time()
        buff = io.BytesIO(pdf_bytes)
        md = upload_and_parse_file(self.api_key, rand_name, buff)
        end = time.time()
        if isinstance(md, bytes):
            md = md.decode("utf-8")

        return {
            "md": md,
            "time": end - start,
        }


def upload_and_parse_file(api_key: str, fname: str, buff, max_retries: int = 180, delay: int = 1):
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }

    # Upload file
    files = {
        'file': (fname, buff, 'application/pdf')
    }
    response = requests.post(
        'https://api.cloud.llamaindex.ai/api/v1/parsing/upload',
        headers=headers,
        files=files
    )
    response.raise_for_status()
    job_id = response.json()['id']

    # Poll for completion
    for _ in range(max_retries):
        status_response = requests.get(
            f'https://api.cloud.llamaindex.ai/api/v1/parsing/job/{job_id}',
            headers=headers
        )
        status_response.raise_for_status()
        if status_response.json()['status'] == 'SUCCESS':
            # Get results
            result_response = requests.get(
                f'https://api.cloud.llamaindex.ai/api/v1/parsing/job/{job_id}/result/markdown',
                headers=headers
            )
            result_response.raise_for_status()
            return result_response.json()['markdown']

        time.sleep(delay)

    raise TimeoutError("Job did not complete within the maximum retry attempts")