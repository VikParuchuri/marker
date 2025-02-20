import json
import time

import requests

from benchmarks.overall.download.base import Downloader


class MathpixDownloader(Downloader):
    service = "mathpix"

    def get_html(self, pdf_bytes):
        headers = {
            "app_id": self.app_id,
            "app_key": self.api_key,
        }
        start = time.time()
        pdf_id = mathpix_request(pdf_bytes, headers)
        status = mathpix_status(pdf_id, headers)
        if status in ["processing", "error"]:
            md = ""
        else:
            md = mathpix_results(pdf_id, headers)
        end = time.time()
        if isinstance(md, bytes):
            md = md.decode("utf-8")

        return {
            "md": md,
            "time": end - start
        }

def mathpix_request(buffer, headers):
    response = requests.post("https://api.mathpix.com/v3/pdf",
        headers=headers,
        data={
            "options_json": json.dumps(
                {
                    "conversion_formats": {
                        "md": True,
                        "html": True
                    }
                }
            )
        },
        files={
            "file": buffer
        }
    )
    data = response.json()
    pdf_id = data["pdf_id"]
    return pdf_id

def mathpix_status(pdf_id, headers):
    max_iters = 120
    i = 0
    status = "processing"
    status2 = "processing"
    while i < max_iters:
        time.sleep(1)
        response = requests.get(f"https://api.mathpix.com/v3/converter/{pdf_id}",
            headers=headers
        )
        status_resp = response.json()
        if "conversion_status" not in status_resp:
            continue
        status = status_resp["conversion_status"]["md"]["status"]
        status2 = status_resp["conversion_status"]["html"]["status"]
        if status == "completed" and status2 == "completed":
            break
        elif status == "error" or status2 == "error":
            break
    out_status = "completed" if status == "completed" and status2 == "completed" else "error"
    return out_status

def mathpix_results(pdf_id, headers, ext="md"):
    response = requests.get(f"https://api.mathpix.com/v3/converter/{pdf_id}.{ext}",
        headers=headers
    )
    return response.content
