import io
import time
import requests

from benchmarks.overall.download.base import Downloader


class MistralDownloader(Downloader):
    service = "mistral"

    def get_html(self, pdf_bytes):
        rand_name = str(time.time()) + ".pdf"
        start = time.time()
        buff = io.BytesIO(pdf_bytes)
        md = upload_and_process_file(self.api_key, rand_name, buff)
        end = time.time()
        if isinstance(md, bytes):
            md = md.decode("utf-8")

        return {
            "md": md,
            "time": end - start,
        }


def upload_and_process_file(api_key: str, fname: str, buff):
    headers = {
        "Authorization": f"Bearer {api_key}"
    }

    upload_headers = headers.copy()
    files = {
        'file': (fname, buff, 'application/pdf'),
        'purpose': (None, 'ocr')
    }

    upload_response = requests.post(
        'https://api.mistral.ai/v1/files',
        headers=upload_headers,
        files=files
    )
    upload_response.raise_for_status()
    file_id = upload_response.json()['id']

    url_headers = headers.copy()
    url_headers["Accept"] = "application/json"

    url_response = requests.get(
        f'https://api.mistral.ai/v1/files/{file_id}/url?expiry=24',
        headers=url_headers
    )
    url_response.raise_for_status()
    signed_url = url_response.json()['url']

    ocr_headers = headers.copy()
    ocr_headers["Content-Type"] = "application/json"

    ocr_data = {
        "model": "mistral-ocr-latest",
        "document": {
            "type": "document_url",
            "document_url": signed_url
        },
        "include_image_base64": True
    }
    ocr_response = requests.post(
        'https://api.mistral.ai/v1/ocr',
        headers=ocr_headers,
        json=ocr_data
    )
    ocr_response.raise_for_status()
    result = ocr_response.json()
    return result["pages"][0]["markdown"]